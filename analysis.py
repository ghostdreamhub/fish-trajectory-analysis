"""FishBehavior58: reproducible CSV analysis, 58-row registry and fixed-anchor scores."""
from __future__ import annotations
import copy, hashlib, json, math, pathlib, sys, warnings
from datetime import datetime
import numpy as np
import pandas as pd
import legacy_metrics as fm

VERSION = '1.2.0'
ASSETS = pathlib.Path(getattr(sys, '_MEIPASS', pathlib.Path(__file__).parent)) / 'assets'
CATALOG = json.loads((ASSETS / 'catalog.json').read_text(encoding='utf-8'))
MAP = {
 5:('wall_zone_pct','%'), 7:('top_third_pct','%'), 8:('freeze_pct','%'),
 12:('speed_median_moving','m/s'),13:('ptm_pct','%'),14:('path_length_m','m'),
 16:('grid_coverage_pct','%'),17:('ptm_pct','%'),18:('speed_mean','m/s'),
 19:('moving_time_s','s'),20:('bouts_per_min','次/min'),21:('turn_rate_median_deg_s','°/s'),
 26:('nnd_median_m','m'),34:('hb_trips_per_min','次/min'),35:('hb_trip_path_mean_m','m'),
 36:('hb_stops_per_trip','次'),38:('corr_dim',''),39:('spatial_entropy_norm',''),
 40:('bout_duration_median_s','s'),41:('ibi_median_s','s'),42:('bout_displacement_median_m','m'),
 43:('bout_peak_speed_median','m/s'),44:('accel_mean_abs','m/s²'),45:('speed_cv',''),
 46:('dist_center_mean_m','m'),47:('fast_pct','%'),48:('centroid_dist_mean_m','m'),
 49:('pair_proximity_mean','0–1'),50:('strength',''),51:('clustering_barrat',''),
 52:('nn_episode_mean_s','s'),53:('pair_nn_freq_mean','次/min'),54:('strongest_partner_share','0–1')}
FINE = {20,21,40,41,42,43,44}
SOCIAL = {26,48,49,50,51,52,53,54}
ACTIVITY = {8,12,13,14,17,18,19,20,21,40,41,42,43,44,45,47}
NOTES = {
 5:'采用贴壁时间比例；中心区时间等其他分量见原始个体指标。',
 7:'仅上三分之一水层比例，属于空间偏好变体；不能替代新异水槽首次进入潜伏期。',
 8:'以速度阈值识别持续低运动片段，未识别姿态；不能直接诊断焦虑。',
 12:'仅运动步速度中位数；静止个体该值缺失，不补零。',
 13:'与 #17 同一计算量，默认仅 #17 进入评分。',
 14:'总路程随观测时长变化，跨实验应统一时长。',
 19:'代表值采用移动时长；路程见原始个体指标。',
 26:'代表值采用最近邻距离；群体平均距离和水平极化度见群体逐帧。未识别领导事件。',
 34:'代表值采用基地外出回合频率；基地为本次观测中停留最长网格。',
 38:'相关维数需合适尺度区间；拟合 R² 不能证明分形结构。',
 49:'个体代表值为与已共同观测伙伴的接近比例算术均值；各鱼对结果单独导出。',
 51:'使用 Barrat 公式；全连通网络可饱和为 1。',
 53:'个体代表值为与已共同观测伙伴最近邻片段频率的算术均值。'}

# Exploratory engineering anchors: weight, lower, upper, direction. These are
# NOT published weights or validated species-independent biological cutoffs.
EXTENDED = {
 5:(2,0,100,'反向'),7:(2,0,100,'正向'),8:(6,0,100,'反向'),
 12:(4,0,.20,'正向'),14:(2,0,12,'正向'),16:(4,0,100,'正向'),
 17:(9,0,100,'正向'),18:(9,0,.20,'正向'),20:(3,0,30,'正向'),
 21:(2,0,180,'正向'),26:(3,0,1,'反向'),34:(3,0,10,'正向'),
 35:(2,0,3,'正向'),36:(2,0,10,'反向'),38:(2,0,3,'正向'),
 39:(3,0,1,'正向'),40:(2,0,10,'正向'),41:(2,0,10,'反向'),
 42:(2,0,1,'正向'),43:(3,0,.50,'正向'),44:(2,0,2,'正向'),
 45:(2,0,2,'正向'),46:(2,0,1,'正向'),47:(5,0,100,'正向'),
 48:(2,0,1,'反向'),49:(3,0,1,'正向'),50:(2,0,5,'正向'),
 51:(1,0,1,'正向'),52:(2,0,30,'正向'),53:(2,0,10,'正向'),54:(1,0,1,'正向')}

def finite(v):
    try: return math.isfinite(float(v))
    except (TypeError, ValueError): return False

def default_config():
    engine = fm.load_config(None)
    engine['corrdim']['max_points'] = 800
    return {'version':VERSION,'engine':engine,'input':{'format':'自动识别','time_unit':'自动','length_unit':'m'},
      'quality':{'min_score_duration_s':30.0,'min_score_coverage_pct':50.0,'min_score_steps':20,
                 'max_bad_step_pct':10.0,'min_available_weight_pct':70.0},
      'scoring':{'name':'31项探索性综合行为方案','calibrated':False,'rules':[
        {'id':m['id'],'weight':EXTENDED.get(m['id'],(0,None,None,'正向'))[0],
         'direction':EXTENDED.get(m['id'],(0,None,None,'正向'))[3],
         'low':EXTENDED.get(m['id'],(0,None,None,'正向'))[1],
         'high':EXTENDED.get(m['id'],(0,None,None,'正向'))[2]}
        for m in CATALOG['metrics']]}}

def validate_config(cfg):
    e=cfg['engine']; q=cfg['quality']; rules=cfg['scoring']['rules']
    for obj,keys in [(e['tank'],['radius_m','water_depth_m']),(e,['v_move_m_s','v_fast_m_s','v_freeze_m_s','freeze_min_s','speed_cap_m_s','grid_cell_m','max_gap_factor'])]:
        for k in keys:
            if not finite(obj[k]) or float(obj[k])<=0: raise ValueError(f'参数 {k} 必须为正数。')
    if e['v_fast_m_s'] <= e['v_move_m_s']: raise ValueError('快速游动阈值必须大于运动阈值。')
    if e['v_move_m_s'] >= e['speed_cap_m_s']: raise ValueError('跳点速度上限必须大于运动阈值。')
    if 2*e['tank']['radius_m']/e['grid_cell_m']>500: raise ValueError('空间网格过密，请增大 grid_cell_m（直径方向最多500格）。')
    if not 4<=e['corrdim']['max_points']<=2000: raise ValueError('相关维数 max_points 须为4–2000，避免内存溢出。')
    if e.get('body_length_m') is not None and (not finite(e['body_length_m']) or e['body_length_m']<=0): raise ValueError('体长须为正数或留空。')
    for k,v in q.items():
        if not finite(v) or float(v)<0 or ('pct' in k and float(v)>100): raise ValueError(f'质量门槛 {k} 无效。')
    if len(rules)!=58 or {r['id'] for r in rules}!=set(range(1,59)): raise ValueError('权重方案必须包含编号 1–58，每个编号恰好一次。')
    for r in rules:
        if not finite(r['weight']) or r['weight']<0: raise ValueError(f"#{r['id']} 权重须为非负数。")
        if r['direction'] not in ['正向','反向']: raise ValueError('指标方向必须为正向或反向。')
        if r['weight']>0 and (not finite(r['low']) or not finite(r['high']) or r['low']>=r['high']):
            raise ValueError(f"#{r['id']} 已启用权重，请设置有效的数值下限、上限（上限大于下限）。")
    if sum(r['weight'] for r in rules)<=0: raise ValueError('至少启用一项指标权重。')

def read_csv(path):
    error=None
    for enc in ['utf-8-sig','gb18030']:
        try: return pd.read_csv(path,encoding=enc,dtype={'fish_id':'string','segment_id':'string','session_id':'string'})
        except UnicodeDecodeError as exc: error=exc
    raise ValueError(f'无法识别 CSV 编码：{path}') from error

def load_inputs(paths,cfg,progress=lambda x:None):
    parts=[]; audit=[]; e=cfg['engine']; inp=cfg['input']
    for path in paths:
        path=pathlib.Path(path); progress(f'读取 {path.name}')
        d=read_csv(path); d.columns=d.columns.str.strip()
        aliases={'鱼编号':'fish_id','鱼ID':'fish_id','id':'fish_id','时间戳':'timestamp_ms',
          'time_s':'timestamp_s','time':'timestamp_s','timestamp':'timestamp_s',
          'X':'x_m','Y':'y_m','Z':'z_m','x':'x_m','y':'y_m','z':'z_m'}
        d=d.rename(columns={a:b for a,b in aliases.items() if a in d and b not in d})
        if d.columns.duplicated().any(): raise ValueError(f'{path.name} 存在重复列名。')
        sim = inp['format']=='仿真原始坐标' or (inp['format']=='自动识别' and 'physics_time_s' in d)
        required=['fish_id','x_m','y_m','z_m']
        missing=[c for c in required if c not in d]
        if missing: raise ValueError(f'{path.name} 缺少列：{", ".join(missing)}。可在模板中查看格式。')
        if d['fish_id'].isna().any(): raise ValueError(f'{path.name} 有空鱼编号。')
        d['fish_id']=d['fish_id'].astype(str).str.strip()
        if d['fish_id'].eq('').any(): raise ValueError('鱼编号不能为空。')
        if 'session_id' in d:
            if d['session_id'].isna().any(): raise ValueError('session_id 存在空值。')
            d['fish_id']=d['session_id'].astype(str)+'::'+d['fish_id']
        for c in ['x_m','y_m','z_m']: d[c]=pd.to_numeric(d[c],errors='coerce')
        scale={'m':1.,'cm':.01,'mm':.001}[inp['length_unit']]
        d[['x_m','y_m','z_m']]*=scale
        if sim:
            oldy=d['y_m'].copy();d['y_m']=d['z_m'];d['z_m']=oldy+e['tank']['water_depth_m']
            if 'physics_time_s' not in d: raise ValueError('仿真格式需要 physics_time_s，避免误用墙钟时间。')
            d['timestamp_ms']=pd.to_numeric(d['physics_time_s'],errors='coerce')*1000
            if 'alive' in d: d['point_type']=np.where(d['alive'].astype(str).str.lower().isin(['1','1.0','true']),'observed','dead')
            audit.append(f'{path.name}：仿真坐标换算为水平 X/Y、离底高度 Z；使用 physics_time_s。')
        else:
            if 'timestamp_ms' in d:
                d['timestamp_ms']=pd.to_numeric(d['timestamp_ms'],errors='coerce')
                if inp['time_unit']=='秒': d['timestamp_ms']*=1000
            elif 'timestamp_s' in d:
                d['timestamp_ms']=pd.to_numeric(d['timestamp_s'],errors='coerce')*(1 if inp['time_unit']=='毫秒' else 1000)
            else: raise ValueError('缺少 timestamp_ms 或 timestamp_s/time_s 时间列。')
        if 'segment_id' not in d:
            d['segment_id']='1';audit.append(f'{path.name}：未提供 segment_id，按单段处理；无法据此确认身份连续。')
        if d['segment_id'].isna().any(): raise ValueError('segment_id 存在空值。')
        if 'point_type' not in d: d['point_type']='observed';audit.append(f'{path.name}：未提供 point_type，按 observed 导入。')
        d['point_type']=d['point_type'].astype(str).str.lower().str.strip()
        unknown=set(d['point_type'])-{'observed','interpolated','predicted','dead'}
        if unknown: raise ValueError(f'未知 point_type：{unknown}')
        if 'confidence' not in d: d['confidence']=np.nan
        d['confidence']=pd.to_numeric(d['confidence'],errors='coerce');d['pos_sd_m']=np.nan
        if 'covariance_m2' in d:
            def sd(v):
                try:
                    a=np.asarray(json.loads(v),float)
                    return float(np.sqrt(np.trace(a))) if a.shape==(3,3) and np.trace(a)>=0 else np.nan
                except (ValueError,TypeError): return np.nan
            d['pos_sd_m']=d['covariance_m2'].map(sd)
        bad=~np.isfinite(d[['x_m','y_m','z_m','timestamp_ms']]).all(axis=1)
        if bad.any(): raise ValueError(f'{path.name} 有 {int(bad.sum())} 条空值/非数值/无穷坐标或时间。请修正后导入。')
        parts.append(d)
    if not parts: raise ValueError('请先选择轨迹 CSV。')
    d=pd.concat(parts,ignore_index=True)
    if len(d)>1500000: raise ValueError('单次最多 150 万行，请按实验拆分。')
    if d.duplicated(['fish_id','timestamp_ms']).any():
        raise ValueError('同一鱼在同一时间有多条记录。请移除重复文件；不同实验请增加 session_id 列。')
    if d['timestamp_ms'].nunique()<2: raise ValueError('至少需要两个不同时间点。')
    # Canonical frame keys use actual shared timestamps, not possibly reused local frame ids.
    d['timestamp_ms']-=d['timestamp_ms'].min()
    times=np.sort(d['timestamp_ms'].unique());d['frame_id']=np.searchsorted(times,d['timestamp_ms'])
    d=d.sort_values(['fish_id','segment_id','timestamp_ms']).reset_index(drop=True)
    return d,audit

def social_safe(pos,kin,ids,frame_dt,cfg):
    """Fixed-time simultaneous frames only; large missing intervals never count as contact."""
    base={f:{k:np.nan for k in ['co_present_time_s','nnd_median_m','centroid_dist_mean_m','strength','clustering_barrat','nn_episode_mean_s','strongest_partner_share']} for f in ids}
    if len(ids)<2 or pos.empty: return base,pd.DataFrame(),pd.DataFrame(),''
    # Legacy social uses regular frames: restrict it to a uniform timestamp lattice explicitly.
    ts=np.sort(pos['timestamp_ms'].unique()); delta=np.diff(ts)/1000
    if len(delta) and not np.allclose(delta/frame_dt,np.round(delta/frame_dt),rtol=0,atol=.001):
        return base,pd.DataFrame(),pd.DataFrame(),'社会指标未计算：时间不在统一采样网格，请同步或重采样后导入。'
    if len(ts)*len(ids)**2>12000000:
        return base,pd.DataFrame(),pd.DataFrame(),'社会指标未计算：同步帧数×鱼数²超出内存保护上限，请分时段分析。'
    pos=pos.copy();kin=kin.copy()
    pos['frame_id']=np.round(pos.timestamp_ms/(frame_dt*1000)).astype('int64')
    if len(kin): kin['frame_id']=np.round(kin.timestamp_ms/(frame_dt*1000)).astype('int64')
    if kin.empty:
        kin=pd.DataFrame(columns=['valid','speed_h','heading','frame_id','fish_id'])
        kin['valid']=kin['valid'].astype(bool)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        soc,pairs,group=fm.social_metrics(pos,kin,ids,frame_dt,cfg)
    for f in ids:
        ps=pairs[pairs.fish_i==f] if len(pairs) else pd.DataFrame()
        if ps.empty:
            soc[f].update({k:np.nan for k in ['strength','clustering_barrat','strongest_partner_share']})
        soc[f]['pair_proximity_mean']=float(ps.proximity_prop.mean()) if len(ps) else np.nan
        soc[f]['pair_nn_freq_mean']=float(ps.nn_episode_freq_per_min.mean()) if len(ps) else np.nan
    return soc,pairs,group,''

def load_supplement(path,ids):
    if not path: return {},[]
    d=read_csv(path);required=['fish_id','metric_id','value','unit','source','protocol']
    if not all(c in d for c in required): raise ValueError('实验指标 CSV 必须含 fish_id,metric_id,value,unit,source,protocol。')
    out={};audit=[];units={}
    for _,r in d.iterrows():
        f=str(r.fish_id);mid=pd.to_numeric(r.metric_id,errors='coerce')
        if f not in ids: raise ValueError(f'补充实验鱼编号 {f} 不在轨迹中。多实验编号需含 session_id:: 前缀。')
        if not finite(mid) or int(mid)!=mid or not 1<=mid<=58: raise ValueError('metric_id 必须为 1–58 整数。')
        mid=int(mid)
        if not finite(r.value): raise ValueError(f'{f} #{mid} 的补充值无效。')
        for c in ['source','protocol','unit']:
            if pd.isna(r[c]) or not str(r[c]).strip(): raise ValueError(f'{f} #{mid} 缺少 {c}，无法追溯实验数据。')
        if (f,mid) in out: raise ValueError(f'实验指标重复：{f} #{mid}')
        if mid in units and units[mid]!=str(r.unit).strip(): raise ValueError(f'#{mid} 的补充实验单位不一致，请先统一单位。')
        units[mid]=str(r.unit).strip()
        if mid in MAP and str(r.unit).strip()!=MAP[mid][1]:
            expected=MAP[mid][1] or '无量纲（此类请使用原始计算值）'
            raise ValueError(f'#{mid} 补充实验单位必须为 {expected}，不自动换算。')
        out[f,mid]={'value':float(r.value),'unit':str(r.unit).strip(),'source':str(r.source),'protocol':str(r.protocol)}
    audit.append(f'补充实验导入 {len(out)} 个鱼×指标值，独立保留来源与实验定义。')
    return out,audit

def analyze(paths,cfg=None,supplement=None,progress=lambda s:None):
    cfg=copy.deepcopy(cfg or default_config());validate_config(cfg)
    d,audit=load_inputs(paths,cfg,progress); e=cfg['engine']
    dif=d.groupby(['fish_id','segment_id'],sort=False).timestamp_ms.diff()/1000
    vals=dif[dif>0]
    if vals.empty: raise ValueError('没有同一鱼、同一片段的连续时间点。')
    frame_dt=float(vals.median());span=float(d.timestamp_ms.max()/1000+frame_dt)
    ids=sorted(d.fish_id.unique()); rows=[];ks=[]
    for i,f in enumerate(ids):
        progress(f'计算个体 {i+1}/{len(ids)}：{f}')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            m,k=fm.fish_metrics(d,f,frame_dt,span,e)
        m['fish_id']=f
        if 'valid' in k:
            m['valid_steps']=int(k.valid.sum());m['valid_step_time_s']=float(k.step_dt.sum())
            ks.append(k)
        else: m['valid_steps']=0;m['valid_step_time_s']=0.
        m['raw_points']=int((d.fish_id==f).sum())
        if frame_dt and vals.max()>e['max_gap_factor']*frame_dt: m['warnings']=m.get('warnings','')+'；存在长缺口，已按片段/间隔限制排除跨缺口运动步'
        rows.append(m)
    per=pd.DataFrame(rows).set_index('fish_id',drop=False)
    progress('计算同步鱼对与群体指标')
    pos=d[d.point_type.isin(e['point_types_position'])]
    kin=pd.concat(ks,ignore_index=True) if ks else pd.DataFrame()
    soc,pairs,group,socwarn=social_safe(pos,kin,ids,frame_dt,e)
    if socwarn: audit.append(socwarn)
    for f,ms in soc.items():
        for k,v in ms.items(): per.loc[f,k]=v
    extras,extraudit=load_supplement(supplement,ids);audit+=extraudit
    result={'version':VERSION,'created':datetime.now().astimezone().isoformat(timespec='seconds'),
      'config':cfg,'input_files':[str(pathlib.Path(p).resolve()) for p in paths],
      'input_sha256':[hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in paths],
      'supplement_file':str(supplement) if supplement else None,
      'supplement_sha256':hashlib.sha256(pathlib.Path(supplement).read_bytes()).hexdigest() if supplement else None,
      'audit':audit,'frame_dt_s':frame_dt,'span_s':span,'rows':len(d),'fish_ids':ids,
      'individual':per.reset_index(drop=True),'pairs':pairs,'group':group,'trajectories':d,
      'supplement':extras,'social_warning':socwarn}
    return rescore(result,cfg)

def rescore(result,cfg):
    validate_config(cfg)
    if any(cfg[k]!=result['config'][k] for k in ['engine','input']):
        raise ValueError('计算参数或输入单位已经改变，请重新分析轨迹后评分。')
    result['config']=copy.deepcopy(cfg);rules={r['id']:r for r in cfg['scoring']['rules']}
    total=sum(r['weight'] for r in rules.values()); details=[];scores=[];e=cfg['engine'];q=cfg['quality']
    custom=any(r['weight']>0 and r['id'] not in ACTIVITY for r in rules.values())
    result['score_title']='探索性综合行为分' if custom else '活跃度分'
    per=result['individual'].set_index('fish_id',drop=False)
    for f in result['fish_ids']:
        m=per.loc[f].to_dict();numer=0.;available=0.;reasons=[];my=[]
        if m.get('valid_steps',0)<q['min_score_steps']: reasons.append('有效运动步不足')
        if m.get('valid_step_time_s',0)<q['min_score_duration_s']: reasons.append('有效运动时长不足')
        if not finite(m.get('coverage_pct')) or m.get('coverage_pct',0)<q['min_score_coverage_pct']: reasons.append('跟踪覆盖率不足')
        if m.get('n_steps_over_cap',0)/max(1,m.get('raw_points',0)-m.get('n_segments',0))*100>q['max_bad_step_pct']: reasons.append('跳点比例过高')
        if m.get('n_outside_tank',0)>0 or m.get('n_above_water',0)>0 or ((result['trajectories'].fish_id==f)&(result['trajectories'].z_m<0)).any(): reasons.append('坐标超出水体边界')
        irregular=False
        fd=result['trajectories'][result['trajectories'].fish_id==f]
        dt=fd.groupby('segment_id').timestamp_ms.diff()/1000
        good=dt[(dt>0)&(dt<=e['max_gap_factor']*result['frame_dt_s'])]
        if len(good): irregular=not np.allclose(good,result['frame_dt_s'],rtol=.05,atol=1e-6)
        for meta in CATALOG['metrics']:
            mid=meta['id'];rule=rules[mid];value=None;unit='';status='缺少条件';reason='需要对应实验装置、事件标注或独立重复实验。';source='';note=NOTES.get(mid,'')
            if mid in MAP:
                key,unit=MAP[mid];value=m.get(key);source=f'轨迹计算：{key}'
                if finite(value):
                    status='已计算';reason=''
                    if m.get('tracked_time_s',0)<e['min_tracked_time_s']: status='谨慎使用';reason='有效跟踪时长低于配置的研究建议时长'
                    if mid in FINE and (1/result['frame_dt_s']<e['min_fps_fine_kinematics'] or irregular):
                        status='不可用';reason='采样率不足或采样不规则，不进入评分'
                    if mid in {5,7,34,35,36}: status='谨慎使用';reason='自由游动情境的变体，不能直接解释为原实验性格'
                else: value=None;reason=result['social_warning'] if mid in SOCIAL and result['social_warning'] else '无满足计算条件的数据（例如无运动回合、同帧同伴或相关维数点数不足）。'
            extra=result['supplement'].get((f,mid))
            if extra:
                value=extra['value'];unit=extra['unit'];status='实验补充';reason='';source=extra['source'];note='实验定义：'+extra['protocol']
            sub=None;contribution=None
            if rule['weight']>0 and finite(value) and status not in ['不可用','缺少条件']:
                sub=100*float(np.clip((float(value)-rule['low'])/(rule['high']-rule['low']),0,1))
                if rule['direction']=='反向':sub=100-sub
                numer+=rule['weight']*sub;available+=rule['weight']
            row={'fish_id':f,'metric_id':mid,'name':meta['name'],'dimension':meta['dimension'].replace('\n',' '),
              'value':float(value) if finite(value) else None,'unit':unit,'status':status,'reason':reason,
              'weight':rule['weight'],'direction':rule['direction'],'low':rule['low'],'high':rule['high'],
              'subscore':sub,'contribution':contribution,'source':source,'notes':note}
            my.append(row)
        weight_pct=100*available/total
        if weight_pct<q['min_available_weight_pct']: reasons.append('可用评分权重不足')
        candidate=numer/available if available>0 else None
        score=candidate if not reasons else None
        label=('低活跃' if score<30 else '中等活跃' if score<70 else '高活跃') if score is not None else '暂不评分'
        if custom and score is not None:label='低分' if score<30 else '中分' if score<70 else '高分'
        for row in my:
            row['contribution']=row['weight']*row['subscore']/available if row['subscore'] is not None and available else None
        details.extend(my)
        scores.append({'fish_id':f,'score':score,'label':label,'score_status':'初始方案，未实验标定' if score is not None else '；'.join(reasons),
          'available_metrics':sum(r['value'] is not None for r in my),'total_metrics':58,
          'scored_metrics':sum(r['subscore'] is not None for r in my),'available_weight_pct':weight_pct,'valid_step_time_s':m.get('valid_step_time_s',0),
          'coverage_pct':m.get('coverage_pct'),'warnings':m.get('warnings','')})
    result['details']=pd.DataFrame(details);result['scores']=pd.DataFrame(scores)
    stats=[]
    for mid,rs in result['details'].groupby('metric_id',sort=True):
        values=rs.value.dropna();valid=rs[rs.status!='不可用'].value.dropna()
        stats.append({'metric_id':mid,'name':rs.iloc[0]['name'],'unit':rs.iloc[0]['unit'],
          'total_fish':len(rs),'numeric_count':len(values),'usable_count':len(valid),'missing_count':int(rs.value.isna().sum()),
          'mean':float(valid.mean()) if len(valid) else None,'median':float(valid.median()) if len(valid) else None,
          'std':float(valid.std(ddof=1)) if len(valid)>1 else None,'min':float(valid.min()) if len(valid) else None,'max':float(valid.max()) if len(valid) else None})
    result['stats']=pd.DataFrame(stats)
    return result

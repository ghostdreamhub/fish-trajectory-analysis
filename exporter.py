"""Fill the bundled, Artifact Tool authored XLSX template; export standalone HTML."""
from __future__ import annotations
import html, json, math, pathlib, re, zipfile
from datetime import datetime
from xml.etree import ElementTree as ET
import numpy as np
import pandas as pd
from analysis import ASSETS,CATALOG,VERSION,finite

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
ET.register_namespace('',NS)

def clean(v):
    if isinstance(v,(dict,list,tuple)):return json.dumps(v,ensure_ascii=False,default=str)
    if v is None:return None
    if isinstance(v,(np.integer,)):return int(v)
    if isinstance(v,(np.floating,)):return float(v) if finite(v) else None
    if isinstance(v,float) and not finite(v):return None
    return v

def clean_json(o):
    if isinstance(o,dict):return {str(k):clean_json(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)):return [clean_json(v) for v in o]
    return clean(o)

def colname(i):
    s=''
    while i:
        i,r=divmod(i-1,26);s=chr(65+r)+s
    return s

def frame_rows(df,headers=None):
    if df.empty and len(df.columns)==0:return [['说明'],['没有符合条件的数据']]
    return [headers or list(df.columns)]+[[clean(v) for v in row] for row in df.itertuples(index=False,name=None)]

def workbook_data(result):
    sc=result['scores'];d=result['details'];st=result['stats']
    summary=frame_rows(sc,['鱼编号','分数（0–100）','分级','评分说明','有数值的指标数','指标总数','实际参与评分项数','可用评分权重（%）','有效运动时长（s）','覆盖率（%）','质量提示'])
    detail=frame_rows(d,['鱼编号','指标编号','指标名称','维度','数值','单位','状态','缺少条件/质量原因','原始权重','方向','数值下限','数值上限','单项分（0–100）','加权贡献（分）','来源','计算说明'])
    stats=frame_rows(st,['编号','指标名称','单位','鱼数','有数值鱼数','可用鱼数','缺失鱼数','均值','中位数','标准差','最小值','最大值'])
    # Quality exports all legacy values with explicit labels, plus added analysis fields.
    per=result['individual'].copy()
    per=per[['fish_id']+[c for c in per.columns if c!='fish_id']]
    per=per.rename(columns={k:f'{v[0]} [{k}]'+(f' ({v[1]})' if v[1] else '') for k,v in __import__('legacy_metrics').METRICS.items()})
    q=frame_rows(per)
    pairs=frame_rows(result['pairs'])
    cfg=[['项目','取值'],['软件版本',VERSION],['生成时间',result['created']],['评分名称',result['score_title']],
      ['评分公式','单项分=100×clip((x−下限)/(上限−下限),0,1)；反向取100−单项分。总分=Σ(可用权重×单项分)/Σ可用权重。'],
      ['权重性质','人工初始方案，未经物种/实验标定。数值下限/上限不是生物学普适界限。'],
      ['缺失处理','不补零；仅在可用权重达到门槛且质量通过时输出分数。可用权重不同的结果应谨慎比较。'],
      ['默认分级','0≤分数<30：低分；30≤分数<70：中分；70≤分数≤100：高分。工程分段，待标定。综合分不能解释为纯活跃度。'],
      ['时间',f"分析使用轨迹时间；观测跨度 {result['span_s']:.4f} s；采样间隔 {result['frame_dt_s']:.6f} s"],
      ['社会指标','共同观测帧按一个采样间隔计时；未共同观测的鱼对不输出接近比例。局部聚类基于已观测网络。'],
      ['58条口径','一条可能包含多个分量，明细采用明确的代表值；变体、来源和不可计算原因逐条列示。']]
    cfg += [['输入文件',p] for p in result['input_files']]
    cfg += [['输入SHA256',p] for p in result['input_sha256']]
    cfg += [['处理记录',p] for p in result['audit']]
    cfg += [['配置JSON',json.dumps(result['config'],ensure_ascii=False)]]
    refs=[['项目','说明'],['指标','指标缺失和适用范围见明细']]
    return [summary,detail,stats,q,pairs,cfg,refs]

def write_xlsx(path,sheets):
    """Use template styles and worksheet layout; values are typed, no macros/formulas."""
    with zipfile.ZipFile(ASSETS/'report_template.xlsx') as src,zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as dst:
        for name in src.namelist():
            data=src.read(name)
            match=re.fullmatch(r'xl/worksheets/sheet(\d+)\.xml',name)
            if match and int(match.group(1))<=len(sheets):
                rows=sheets[int(match.group(1))-1]
                if len(rows)>1048576:raise ValueError('Excel 工作表行数超过上限，请分批导出。')
                root=ET.fromstring(data);sd=root.find(f'{{{NS}}}sheetData')
                if sd is None:sd=ET.SubElement(root,f'{{{NS}}}sheetData')
                styles={}
                for r in sd:
                    for c in r:
                        styles[c.attrib.get('r')]=c.attrib.get('s','0')
                header_style=styles.get('A1','0');body_style=styles.get('A2','0');float_style=styles.get('B2',body_style)
                sd.clear();ncols=max(len(r) for r in rows)
                for ri,values in enumerate(rows,1):
                    rr=ET.SubElement(sd,f'{{{NS}}}row',{'r':str(ri),'ht':'34' if ri==1 else '32','customHeight':'1'})
                    for ci,v in enumerate(values,1):
                        v=clean(v)
                        if v is None:continue
                        attrs={'r':f'{colname(ci)}{ri}','s':header_style if ri==1 else float_style if isinstance(v,float) else body_style}
                        cell=ET.SubElement(rr,f'{{{NS}}}c',attrs)
                        if isinstance(v,(int,float)) and not isinstance(v,bool):ET.SubElement(cell,f'{{{NS}}}v').text=str(v)
                        else:
                            cell.set('t','inlineStr');ss=ET.SubElement(cell,f'{{{NS}}}is');tt=ET.SubElement(ss,f'{{{NS}}}t')
                            tt.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
                            tt.text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(v))[:32767]
                dim=root.find(f'{{{NS}}}dimension')
                if dim is None:dim=ET.Element(f'{{{NS}}}dimension');root.insert(0,dim)
                dim.set('ref',f'A1:{colname(ncols)}{len(rows)}')
                af=root.find(f'{{{NS}}}autoFilter')
                if af is None:af=ET.SubElement(root,f'{{{NS}}}autoFilter')
                af.set('ref',f'A1:{colname(ncols)}{len(rows)}')
                data=ET.tostring(root,encoding='utf-8',xml_declaration=True)
            dst.writestr(name,data)

def fmt(v):
    if v is None or isinstance(v,float) and not finite(v):return '—'
    if isinstance(v,(float,np.floating)):return f'{v:.4g}'
    return str(v)

def table(df,cols,headers):
    esc=lambda v:html.escape(fmt(v))
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(s)+'</th>' for s in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(r[c])+'</td>' for c in cols)+'</tr>' for r in df.to_dict('records'))+'</tbody></table></div>'

def trajectory_svg(df):
    points=[];colors=['#008c95','#5974df','#e09342','#b864b4','#419c67']
    for j,(fid,fish) in enumerate(df.groupby('fish_id',sort=True)):
        if j>=30:break
        for _,g in fish.groupby('segment_id',sort=False):
            if len(g)>800:g=g.iloc[np.linspace(0,len(g)-1,800).astype(int)]
            points.append((j,g[['x_m','y_m']].to_numpy()))
    if not points:return ''
    p=np.concatenate([v for _,v in points]);mn=p.min(0);span=np.maximum(p.max(0)-mn,.01)
    paths=''
    for j,p in points:
        xy=(p-mn)/span*np.array([680,250])+[30,25]
        paths+=f'<polyline fill="none" stroke="{colors[j%len(colors)]}" stroke-width="1.3" opacity=".7" points="'+ ' '.join(f'{x:.1f},{300-y:.1f}' for x,y in xy)+'"/>'
    return '<svg viewBox="0 0 740 310" role="img" aria-label="三维轨迹的水平投影">'+paths+'</svg>'

def write_html(path,r):
    e=html.escape;sc=r['scores'];scores=sc.score.dropna();mean=float(scores.mean()) if len(scores) else None
    bars=''.join(f'<div class="barrow"><span>{e(str(v.fish_id))}</span><div class="track"><div style="width:{float(v.score):.2f}%"></div></div><strong>{float(v.score):.1f}</strong></div>' for v in sc.itertuples() if finite(v.score))
    byfish=[]
    for fid,g in r['details'].groupby('fish_id',sort=True):
        byfish.append('<details><summary>'+e(str(fid))+' · 58 条指标</summary>'+table(g,['metric_id','name','value','unit','status','weight','subscore','reason','notes'],['编号','指标','数值','单位','状态','权重','单项分','原因','说明'])+'</details>')

    notices=''.join('<li>'+e(str(x))+'</li>' for x in r['audit']) or '<li>未记录额外导入转换。</li>'
    text=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>鱼类轨迹分析报告</title>
<style>body{{font:15px "Microsoft YaHei",Arial,sans-serif;color:#183446;background:#edf3f7;margin:0}}main{{max-width:1140px;margin:auto;padding:36px}}h1{{font-size:29px;margin:8px 0}}h2{{font-size:20px}}.muted{{color:#607687}}.hero,.panel{{background:white;border:1px solid #dce6eb;border-radius:14px;padding:26px;margin:20px 0}}.hero{{border-top:5px solid #008c95}}.cards{{display:flex;gap:16px;flex-wrap:wrap}}.card{{flex:1;min-width:130px;background:#f2f8f9;padding:18px;border-radius:9px}}.card strong{{display:block;font-size:30px;color:#00818a;margin:5px 0}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid #e3eaef;vertical-align:top;max-width:380px;overflow-wrap:anywhere}}th{{background:#eaf4f5;position:sticky;top:0}}.scroll{{overflow:auto;max-height:650px}}details{{margin:12px 0;border:1px solid #dce6eb;border-radius:8px;padding:14px}}summary{{cursor:pointer;font-weight:bold}}.barrow{{display:flex;gap:15px;align-items:center;margin:10px 0}}.barrow span{{width:150px;overflow-wrap:anywhere}}.track{{background:#e7eef3;height:13px;flex:1;border-radius:7px;overflow:hidden}}.track div{{height:100%;background:#008c95}}button{{background:#008c95;color:white;border:0;padding:10px 18px;border-radius:6px;cursor:pointer}}.note{{background:#fff6df;border-left:4px solid #d99a22;padding:15px;line-height:1.8}}svg{{width:100%;max-height:350px}}li{{line-height:1.8}}@media print{{body{{background:white}}main{{padding:0}}button{{display:none}}details{{break-inside:avoid}}.scroll{{max-height:none;overflow:visible}}.panel{{break-inside:auto}}th{{position:static}}}}</style>
<main><div class="hero"><div class="muted">FISH BEHAVIOR 58 · v{VERSION}</div><h1>鱼类三维轨迹行为分析报告</h1><p class="muted">生成时间：{e(r['created'])}</p><button onclick="document.querySelectorAll('details').forEach(x=>x.open=true);window.print()">打印 / 保存为 PDF</button></div>
<div class="cards"><div class="card">分析鱼数<strong>{len(sc)}</strong>个体编号</div><div class="card">轨迹点数<strong>{r['rows']:,}</strong>CSV 原始记录</div><div class="card">指标库<strong>58</strong>逐项记录可用性</div><div class="card">平均{e(r['score_title'])}<strong>{fmt(mean)}</strong>可评分 {len(scores)} / {len(sc)} 尾</div></div>
<div class="panel"><h2>评分解释</h2><div class="note">当前方案：{e(r['config']['scoring']['name'])}，启用 {sum(x['weight']>0 for x in r['config']['scoring']['rules'])} 项。权重、方向与上下限均为待标定的工程初值。运动、空间及社会指标组成的综合分不能直接解释为活跃度或稳定性格。</div><p>单项分 = 100 × clip((数值 − 下限) / (上限 − 下限), 0, 1)，反向指标取 100 − 单项分。总分 = Σ(可用权重 × 单项分) / Σ可用权重。缺失值不补零，质量门槛未通过则不评分。低、中、高分界限为工程初值，可用权重不同的个体应谨慎比较。</p>{bars}</div>
<div class="panel"><h2>个体评分与质量</h2>{table(sc,['fish_id','score','label','score_status','available_metrics','scored_metrics','available_weight_pct','valid_step_time_s','coverage_pct'],['鱼编号','分数','分级','说明','有数值指标数 / 58','实际计分项数','可用权重 %','有效运动时长 s','覆盖率 %'])}</div>
<div class="panel"><h2>轨迹水平投影</h2>{trajectory_svg(r['trajectories'])}<p class="muted">最多展示前30尾鱼，每片段最多800个绘图点。完整轨迹仍保存在输入CSV中。</p></div>
<div class="panel"><h2>58 条指标统计</h2><p>统计仅纳入有数值且未标为“不可用”的个体；谨慎使用与实验补充值保留并在明细中注明。不同实验定义的补充值需先统一口径。标准差采用样本标准差。</p>{table(r['stats'],['metric_id','name','unit','usable_count','missing_count','mean','median','std','min','max'],['编号','指标','单位','可用鱼数','缺失鱼数','均值','中位数','标准差','最小','最大'])}</div>
<div class="panel"><h2>逐鱼指标明细</h2>{''.join(byfish)}</div>
<div class="panel"><h2>数据来源与处理</h2><p>轨迹时间跨度：{r['span_s']:.3f} 秒；采样间隔中位数：{r['frame_dt_s']:.6f} 秒。时间来自轨迹时间列，仿真采用物理推进时间。</p><ul>{notices}</ul><p>输入文件：</p><ul>{''.join('<li>'+e(x)+'</li>' for x in r['input_files'])}</ul><p>完整参数、文件校验值、鱼对结果及原始个体特征见同目录 Excel、CSV、JSON。</p></div>
</main></html>'''
    pathlib.Path(path).write_text(text,encoding='utf-8')

def export_all(result,folder,progress=lambda s:None):
    folder=pathlib.Path(folder);folder.mkdir(parents=True,exist_ok=True)
    progress('导出 Excel 与 CSV')
    write_xlsx(folder/'58项指标分析.xlsx',workbook_data(result))
    names={'scores':'个体评分.csv','details':'58项指标明细.csv','stats':'58项指标统计.csv','individual':'原始个体特征.csv','pairs':'鱼对关系.csv','group':'群体逐帧.csv'}
    for key,name in names.items(): result[key].to_csv(folder/name,index=False,encoding='utf-8-sig')
    (folder/'分析参数与权重.json').write_text(json.dumps(clean_json(result['config']),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    audit={k:result[k] for k in ['version','created','input_files','input_sha256','supplement_file','supplement_sha256','audit','frame_dt_s','span_s','rows','fish_ids','score_title']}
    (folder/'数据来源与处理记录.json').write_text(json.dumps(clean_json(audit),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    progress('生成独立 HTML 分析报告')
    write_html(folder/'鱼类行为分析报告.html',result)
    return folder

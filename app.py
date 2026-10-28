"""Native Windows frontend and bundled command-line verification entry point."""
from __future__ import annotations
import argparse, copy, json, math, os, pathlib, queue, sys, threading, traceback
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import customtkinter as ctk
from analysis import ASSETS,CATALOG,MAP,VERSION,default_config,validate_config,analyze,rescore,finite
from exporter import export_all,fmt

BG='#F3F6FA';INK='#172F42';TEAL='#087F8C';MUTED='#526A7F';NAV='#102C3C'
FONT='Microsoft YaHei UI'
ctk.set_appearance_mode('light')
ctk.set_default_color_theme('blue')

class RoundButton(ctk.CTkButton):
    def __init__(self,parent,text,command,primary=False,dark=False,**kw):
        super().__init__(parent,text=text,command=command,corner_radius=12,height=40,
          font=(FONT,14,'bold' if primary else 'normal'),
          fg_color=('#18B7A0' if dark else TEAL) if primary else ('#1D4154' if dark else '#EAF1F6'),
          hover_color=('#35C9B4' if dark else '#066976') if primary else ('#2D5265' if dark else '#DBE8F0'),
          text_color=('#092E36' if dark and primary else '#FFFFFF') if (primary or dark) else INK,
          text_color_disabled='#859BA8',border_width=0,**kw)
    def state(self,spec):
        self.configure(state='disabled' if 'disabled' in spec else 'normal')

class RoundTabs(ctk.CTkFrame):
    def __init__(self,parent):
        super().__init__(parent,fg_color='transparent',corner_radius=0)
        self.page_names=[];self.pages={}
        self.selector=ctk.CTkSegmentedButton(self,values=[],command=self.select,height=42,corner_radius=12,
          border_width=5,fg_color='#E3EBF3',selected_color='white',selected_hover_color='#E5F5F2',
          unselected_color='#E3EBF3',unselected_hover_color='#D2E2EE',text_color=INK,font=(FONT,14,'bold'))
        self.selector.pack(anchor='w',pady=(0,12))
        self.host=ctk.CTkFrame(self,corner_radius=20,border_width=1,border_color='#E0E8F0',fg_color='white')
        self.host.pack(fill='both',expand=True)
    def add(self,name):
        frame=ctk.CTkFrame(self.host,fg_color='white',corner_radius=0)
        self.pages[name]=frame;self.page_names.append(name);self.selector.configure(values=self.page_names)
        if len(self.page_names)==1:self.select(name)
        return frame
    def select(self,name):
        for page in self.pages.values():page.pack_forget()
        self.pages[name].pack(fill='both',expand=True,padx=12,pady=14);self.selector.set(name)
    def tabs(self):return tuple(self.page_names)

class StripeTree(ttk.Treeview):
    def insert(self,parent,index,**kwargs):
        tags=tuple(kwargs.get('tags',()))
        if len(self.get_children(parent))%2:tags+=('stripe',)
        kwargs['tags']=tags
        return super().insert(parent,index,**kwargs)

class App(ctk.CTk):
    def __init__(self):
        super().__init__();self.title('鱼类三维轨迹行为分析 · Fish Behavior 58')
        self.geometry('1440x900');self.minsize(1120,760);self.configure(fg_color=BG)
        self.cfg=default_config();self.paths=[];self.supplement=None;self.result=None
        self.bus=queue.Queue();self.busy=False;self.last_export=None;self.after_job=None
        self.option_add('*Font',(FONT,10))
        self.dpi=max(1.,self.winfo_fpixels('1i')/96.)
        st=ttk.Style(self);st.theme_use('clam')
        st.configure('.',font=(FONT,10),background='white',foreground=INK)
        st.configure('TButton',padding=(12,9),background='#EAF1F6',borderwidth=0)
        st.configure('Accent.TButton',background=TEAL,foreground='white',font=(FONT,10,'bold'))
        st.map('Accent.TButton',background=[('active','#066976'),('disabled','#B8CCD3')])
        st.configure('Treeview',background='white',fieldbackground='white',
          rowheight=round(46*self.dpi),font=(FONT,14),borderwidth=0,relief='flat')
        st.configure('Treeview.Heading',background='#EAF1F7',foreground='#2B485F',
          padding=(10,12),font=(FONT,12,'bold'),borderwidth=0,relief='flat')
        st.map('Treeview',background=[('selected','#D5F1F0')],foreground=[('selected','#075C66')])
        st.map('Treeview.Heading',background=[('active','#DEEAF3')])
        self._build();self.protocol('WM_DELETE_WINDOW',self.close);self.after(150,self.poll)

    def label(self,parent,text,size=14,color=INK,bold=False,**kw):
        return ctk.CTkLabel(parent,text=text,text_color=color,font=(FONT,size,'bold' if bold else 'normal'),**kw)

    def _build(self):
        self.grid_rowconfigure(0,weight=1);self.grid_columnconfigure(1,weight=1)
        nav=ctk.CTkFrame(self,width=286,corner_radius=0,fg_color=NAV)
        nav.grid(row=0,column=0,sticky='nsew');nav.grid_propagate(False)
        nav.grid_columnconfigure(0,weight=1);nav.grid_rowconfigure(1,weight=1)
        brand=ctk.CTkFrame(nav,fg_color='transparent');brand.grid(row=0,column=0,sticky='ew',padx=22,pady=(26,12))
        badge=ctk.CTkFrame(brand,width=48,height=48,corner_radius=15,fg_color='#1B5161');badge.pack(side='left');badge.pack_propagate(False)
        self.label(badge,'58',22,'#72E3D1',True).pack(expand=True)
        bt=ctk.CTkFrame(brand,fg_color='transparent');bt.pack(side='left',padx=12)
        self.label(bt,'FISH BEHAVIOR',17,'white',True).pack(anchor='w')
        self.label(bt,'三维轨迹行为分析',12,'#ACC6D5').pack(anchor='w',pady=(1,0))
        scroll=ctk.CTkScrollableFrame(nav,fg_color=NAV,corner_radius=0,scrollbar_button_color='#2B5063',scrollbar_button_hover_color='#416D80')
        scroll.grid(row=1,column=0,sticky='nsew',padx=(12,8),pady=0)
        self.label(scroll,'数据导入',12,'#9EBACA',True).pack(anchor='w',padx=10,pady=(8,10))
        for text,cmd,accent in [('导入轨迹 CSV',self.choose,True),('补充实验指标',self.choose_supp,False),('保存 CSV 模板',self.templates,False)]:
            RoundButton(scroll,text,cmd,primary=accent,dark=True).pack(fill='x',padx=10,pady=(0,8))
        filecard=ctk.CTkFrame(scroll,corner_radius=12,fg_color='#193A4D');filecard.pack(fill='x',padx=10,pady=(4,16))
        self.file_label=self.label(filecard,'尚未选择轨迹文件',12,'#C2D7E4',anchor='w',justify='left',wraplength=206)
        self.file_label.pack(fill='x',padx=12,pady=12)
        self.label(scroll,'实验参数',12,'#9EBACA',True).pack(anchor='w',padx=10,pady=(2,8))
        self.form={}
        for key,label,value in [('radius','水槽半径  /  m',1),('depth','水深  /  m',.9),('body','体长  /  m，可留空',''),('move','运动阈值  /  m/s',.0175),('fast','快速阈值  /  m/s',.2)]:
            self.label(scroll,label,12,'#BDD0DD').pack(anchor='w',padx=12,pady=(5,3))
            v=tk.StringVar(value=str(value));ctk.CTkEntry(scroll,textvariable=v,height=36,corner_radius=10,
              border_width=1,border_color='#34566B',fg_color='#1A3A4E',text_color='#F3FAFE',font=(FONT,14)).pack(fill='x',padx=10,pady=(0,3));self.form[key]=v
        self.formatvar=tk.StringVar(value='自动识别')
        self.label(scroll,'坐标格式',12,'#BDD0DD').pack(anchor='w',padx=12,pady=(10,3))
        ctk.CTkComboBox(scroll,variable=self.formatvar,values=['自动识别','标准三维坐标','仿真原始坐标'],state='readonly',height=36,
          corner_radius=10,border_width=1,border_color='#34566B',fg_color='#1A3A4E',button_color='#34566B',
          button_hover_color='#476B80',text_color='white',font=(FONT,13),dropdown_font=(FONT,13)).pack(fill='x',padx=10,pady=(0,10))
        actions=ctk.CTkFrame(nav,fg_color=NAV,corner_radius=0);actions.grid(row=2,column=0,sticky='ew',padx=22,pady=(12,16))
        self.analyze_btn=RoundButton(actions,'开始分析',self.start,primary=True,dark=True);self.analyze_btn.pack(fill='x',pady=(0,9))
        self.export_btn=RoundButton(actions,'导出报告与 Excel',self.export,dark=True);self.export_btn.pack(fill='x',pady=(0,8))
        ctk.CTkButton(actions,text='高级参数与质量门槛',command=self.advanced,height=28,corner_radius=9,
          fg_color='transparent',hover_color='#1D4154',text_color='#B4CBD9',font=(FONT,12)).pack(fill='x')
        self.label(actions,f'v{VERSION}  ·  本地离线分析',11,'#8CAABB').pack(pady=(10,0))
        main=ctk.CTkFrame(self,fg_color='transparent');main.grid(row=0,column=1,sticky='nsew',padx=(26,28),pady=(24,18))
        header=ctk.CTkFrame(main,fg_color='transparent');header.pack(fill='x',pady=(0,18))
        heading=ctk.CTkFrame(header,fg_color='transparent');heading.pack(side='left',fill='x',expand=True)
        self.label(heading,'鱼类三维轨迹行为分析',27,INK,True).pack(anchor='w')
        self.label(heading,'从轨迹数据到行为特征，让每项结果清晰可查。',14,MUTED).pack(anchor='w',pady=(5,0))
        pill=ctk.CTkFrame(header,corner_radius=14,fg_color='#E0F2EE');pill.pack(side='right',anchor='n',pady=8)
        self.label(pill,'本地运行  /  CSV',12,'#126C63',True).pack(padx=15,pady=7)
        cards=ctk.CTkFrame(main,fg_color='transparent');cards.pack(fill='x')
        self.cards={}
        colors=[('#E8F6F3','#087F75'),('#EDF2FD','#4867B3'),('#EDF6FC','#2876A6'),('#F2EEFB','#7951AB')]
        for i,(label,key,val,sub) in enumerate([('分析个体','fish','—','按鱼编号分别统计'),('轨迹点数','points','—','导入的有效坐标记录'),('指标清单','metrics','58','完整指标清单'),('可评分个体','scorable','—','通过评分质量门槛')]):
            f=ctk.CTkFrame(cards,corner_radius=18,fg_color='white',border_width=1,border_color='#E4EBF2')
            f.grid(row=0,column=i,sticky='nsew',padx=(0,12 if i<3 else 0));cards.grid_columnconfigure(i,weight=1,uniform='cards')
            tag=ctk.CTkFrame(f,fg_color=colors[i][0],corner_radius=8);tag.pack(anchor='w',padx=17,pady=(17,5))
            self.label(tag,label,12,colors[i][1],True).pack(padx=9,pady=3)
            v=self.label(f,val,32,INK,True,anchor='w');v.pack(fill='x',padx=18,pady=(0,1));self.cards[key]=v
            self.label(f,sub,11,MUTED,anchor='w').pack(fill='x',padx=18,pady=(0,15))
        notice=ctk.CTkFrame(main,corner_radius=12,fg_color='#FFF5DF',border_width=1,border_color='#F3E5BF');notice.pack(fill='x',pady=(15,12))
        self.note=self.label(notice,'评分说明  ·  初始权重尚未实验标定；缺少条件的指标会注明原因。',13,'#85631F',anchor='w',wraplength=1000)
        self.note.pack(fill='x',padx=16,pady=11)
        nb=RoundTabs(main);nb.pack(fill='both',expand=True);self.nb=nb
        self.tabs={name:nb.add(name) for name in ['结果总览','58 项指标','权重与评分','轨迹预览','方法与说明']}
        overview=self.tabs['结果总览']
        top=ctk.CTkFrame(overview,fg_color='transparent');top.pack(fill='x',padx=10,pady=(12,16));top.grid_columnconfigure(0,weight=3);top.grid_columnconfigure(1,weight=2)
        scorecard=ctk.CTkFrame(top,corner_radius=16,fg_color='#F5FAFC');scorecard.grid(row=0,column=0,sticky='nsew',padx=(0,14))
        self.gauge_caption=self.label(scorecard,'平均探索性综合行为分',13,MUTED,anchor='w');self.gauge_caption.pack(fill='x',padx=18,pady=(16,1))
        grow=ctk.CTkFrame(scorecard,fg_color='transparent');grow.pack(fill='x',padx=18)
        self.gauge_number=self.label(grow,'—',36,TEAL,True);self.gauge_number.pack(side='left')
        self.label(grow,'/ 100',14,MUTED).pack(side='right',anchor='s',pady=9)
        self.gauge_bar=ctk.CTkProgressBar(scorecard,height=10,corner_radius=5,fg_color='#DEE9F0',progress_color='#159D99');self.gauge_bar.pack(fill='x',padx=18,pady=(8,4));self.gauge_bar.set(0)
        endpoints=ctk.CTkFrame(scorecard,fg_color='transparent');endpoints.pack(fill='x',padx=18,pady=(0,14))
        self.label(endpoints,'0  低分',11,MUTED).pack(side='left');self.label(endpoints,'高分  100',11,MUTED).pack(side='right')
        self.gauge_value=None
        infocard=ctk.CTkFrame(top,corner_radius=16,fg_color='#F5F7FB');infocard.grid(row=0,column=1,sticky='nsew')
        self.label(infocard,'数据与质量概览',14,INK,True,anchor='w').pack(fill='x',padx=18,pady=(18,6))
        self.summary=self.label(infocard,'等待导入 CSV\n支持标准轨迹与本项目仿真格式。',13,MUTED,justify='left',anchor='w',wraplength=310)
        self.summary.pack(fill='both',expand=True,padx=18,pady=(0,18))
        self.scoretree=self.tree(overview,[('fish','鱼编号',150),('score','分数',85),('label','分级',100),('n','有数值项 / 58',120),('scored','实际计分项',100),('weight','可用权重 %',110),('quality','评分说明',300)])
        self.scoretree.bind('<<TreeviewSelect>>',self.select_fish);self.draw_gauge(None)
        dtab=self.tabs['58 项指标'];bar=ctk.CTkFrame(dtab,fg_color='transparent');bar.pack(fill='x',padx=12,pady=(14,12))
        self.fishvar=tk.StringVar();self.fishbox=ctk.CTkComboBox(bar,variable=self.fishvar,state='readonly',values=[],width=200,height=36,corner_radius=10,font=(FONT,13),command=lambda _:self.refresh_details())
        self.fishbox.pack(side='left')
        self.filtervar=tk.StringVar(value='全部指标');ctk.CTkComboBox(bar,variable=self.filtervar,state='readonly',values=['全部指标','有数值','缺少条件','参与评分'],width=140,height=36,corner_radius=10,font=(FONT,13),command=lambda _:self.refresh_details()).pack(side='left',padx=10)
        self.label(bar,'双击查看指标详情',12,MUTED).pack(side='right',padx=4)
        self.detailtree=self.tree(dtab,[('id','编号',55),('name','指标名称',300),('val','数值',95),('unit','单位',80),('status','状态',100),('w','权重',65),('score','单项分',80),('reason','说明',360)])
        self.detailtree.bind('<Double-1>',self.show_metric)
        wtab=self.tabs['权重与评分'];bar=ctk.CTkFrame(wtab,fg_color='transparent');bar.pack(fill='x',padx=12,pady=(14,10))
        for text,cmd in [('编辑选中项',self.edit_weight),('恢复初始权重',self.reset_weights),('导入方案',self.load_scheme),('保存方案',self.save_scheme)]:RoundButton(bar,text,cmd).pack(side='left',padx=(0,8))
        hint=ctk.CTkFrame(wtab,corner_radius=12,fg_color='#F0F7FA');hint.pack(fill='x',padx=12,pady=(0,12))
        self.label(hint,'默认启用 31 条，包含运动、空间和社会行为；权重、方向和上下限为待标定初值。\n双击指标页可查看计算说明。该综合分不能直接等同于活跃度。',12,MUTED,justify='left',anchor='w',wraplength=1000).pack(fill='x',padx=14,pady=12)
        self.weighttree=self.tree(wtab,[('id','编号',55),('name','指标',300),('w','原始权重',95),('dir','方向',75),('lo','数值下限',105),('hi','数值上限',105),('type','初始用途',160)])
        self.weighttree.bind('<Double-1>',lambda e:self.edit_weight());self.refresh_weights()
        plot=self.tabs['轨迹预览'];self.label(plot,'左侧：水平 X/Y 投影   /   右侧：X/Z 侧视投影。按轨迹片段分别绘制。',13,MUTED,anchor='w').pack(fill='x',padx=16,pady=(16,8))
        self.plot=tk.Canvas(plot,bg='white',highlightthickness=0);self.plot.pack(fill='both',expand=True,padx=14,pady=12);self.plot.bind('<Configure>',lambda e:self.draw_plot())
        txt=ctk.CTkTextbox(self.tabs['方法与说明'],wrap='word',corner_radius=12,fg_color='#F7FAFC',text_color=INK,font=(FONT,14),spacing1=4,spacing3=8)
        txt.pack(fill='both',expand=True,padx=12,pady=14);txt.insert('1.0',HELP);txt.configure(state='disabled')
        bottom=ctk.CTkFrame(main,fg_color='transparent');bottom.pack(fill='x',pady=(12,0))
        self.status=tk.StringVar(value='就绪 · 数据仅在本地处理');ctk.CTkLabel(bottom,textvariable=self.status,text_color=MUTED,font=(FONT,12),anchor='w').pack(side='left')
        self.progress=ttk.Progressbar(bottom,mode='indeterminate',length=150);self.progress.pack(side='right')

    def tree(self,parent,cols):
        shell=ctk.CTkFrame(parent,corner_radius=14,fg_color='#E5EDF4');shell.pack(fill='both',expand=True,padx=12,pady=(0,14))
        frame=tk.Frame(shell,bg='white');frame.pack(fill='both',expand=True,padx=2,pady=10)
        t=StripeTree(frame,columns=[c[0] for c in cols],show='headings',selectmode='browse')
        for key,label,width in cols:t.heading(key,text=label);t.column(key,width=round(width*self.dpi),minwidth=round(45*self.dpi),stretch=key in ['name','reason','quality'])
        y=ctk.CTkScrollbar(frame,orientation='vertical',command=t.yview,fg_color='white',button_color='#C5D3DF',button_hover_color='#8CAABA',width=14,corner_radius=7)
        x=ctk.CTkScrollbar(frame,orientation='horizontal',command=t.xview,fg_color='white',button_color='#C5D3DF',button_hover_color='#8CAABA',height=14,corner_radius=7)
        t.configure(yscrollcommand=y.set,xscrollcommand=x.set);t.grid(row=0,column=0,sticky='nsew');y.grid(row=0,column=1,sticky='ns');x.grid(row=1,column=0,sticky='ew');frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        t.tag_configure('missing',foreground='#667C8D');t.tag_configure('warning',foreground='#9A6318');t.tag_configure('stripe',background='#F5F8FC');return t

    def choose(self):
        paths=filedialog.askopenfilenames(title='选择轨迹 CSV（可多选同一实验的分时文件）',filetypes=[('CSV 文件','*.csv')])
        if paths:self.paths=list(paths);self.file_label.configure(text=f'已选择 {len(paths)} 个轨迹文件\n'+pathlib.Path(paths[0]).name)

    def choose_supp(self):
        p=filedialog.askopenfilename(title='选择补充实验指标 CSV',filetypes=[('CSV 文件','*.csv')])
        if p:self.supplement=p;self.file_label.configure(text=f'轨迹 {len(self.paths)} 个文件\n补充实验：{pathlib.Path(p).name}')

    def templates(self):
        folder=filedialog.askdirectory(title='保存 CSV 模板与示例')
        if folder:
            import shutil
            for p in (ASSETS/'examples').glob('*'):shutil.copy2(p,pathlib.Path(folder)/p.name)
            messagebox.showinfo('模板已保存','已保存标准轨迹模板、补充实验模板与标记为合成的示例数据。')

    def get_config(self):
        c=copy.deepcopy(self.cfg);e=c['engine']
        e['tank']={'radius_m':float(self.form['radius'].get()),'water_depth_m':float(self.form['depth'].get())}
        e['body_length_m']=float(self.form['body'].get()) if self.form['body'].get().strip() else None
        oldmove=e['v_move_m_s'];e['v_move_m_s']=float(self.form['move'].get())
        if e['v_freeze_m_s']==oldmove:e['v_freeze_m_s']=e['v_move_m_s']
        e['v_fast_m_s']=float(self.form['fast'].get())
        c['input']['format']=self.formatvar.get();validate_config(c);return c

    def set_config(self,c):
        validate_config(c);self.cfg=copy.deepcopy(c);e=c['engine']
        for k,v in [('radius',e['tank']['radius_m']),('depth',e['tank']['water_depth_m']),('body',e.get('body_length_m') or ''),('move',e['v_move_m_s']),('fast',e['v_fast_m_s'])]:self.form[k].set(str(v))
        self.formatvar.set(c['input']['format']);self.refresh_weights()
        self.result=None;self.scoretree.delete(*self.scoretree.get_children());self.detailtree.delete(*self.detailtree.get_children())
        self.fishbox.configure(values=[]);self.fishvar.set('');self.draw_gauge(None);self.draw_plot()
        for key in ['fish','points','scorable']:self.cards[key].configure(text='—')
        self.summary.configure(text='参数方案已更新，请重新点击开始分析。')

    def task(self,fn):
        if self.busy:return
        self.busy=True;self.analyze_btn.state(['disabled']);self.export_btn.state(['disabled']);self.progress.start(12)
        def worker():
            try:self.bus.put(('done',fn()))
            except BaseException as exc:self.bus.put(('error',(str(exc),traceback.format_exc())))
        threading.Thread(target=worker,daemon=True).start()

    def start(self):
        if self.busy:return
        if not self.paths:messagebox.showinfo('导入数据','请先导入轨迹 CSV。');return
        try:c=self.get_config()
        except Exception as e:messagebox.showerror('参数错误',str(e));return
        self.cfg=c;paths=list(self.paths);supp=self.supplement
        self.task(lambda:('analysis',analyze(paths,c,supp,lambda s:self.bus.put(('status',s)))))

    def poll(self):
        try:
            while True:
                kind,value=self.bus.get_nowait()
                if kind=='status':self.status.set(value)
                elif kind=='error':
                    self.endtask();self.status.set('处理失败：'+value[0]);messagebox.showerror('处理失败',value[0])
                    log=pathlib.Path(os.environ.get('LOCALAPPDATA',str(pathlib.Path.home())))/'FishBehavior58';log.mkdir(parents=True,exist_ok=True);(log/'last_error.log').write_text(value[1],encoding='utf-8')
                else:
                    self.endtask();op,data=value
                    if op=='analysis':self.result=data;self.refresh();self.status.set('分析完成 · 可查看指标或导出报告')
                    else:
                        self.last_export=data;self.status.set('导出完成：'+str(data))
                        if not self.after_job:messagebox.showinfo('导出完成',f'报告、Excel、CSV 和参数已保存到：\n{data}')
                    if self.after_job:self.after_job(op,data)
        except queue.Empty:pass
        self.after(120,self.poll)

    def endtask(self):
        self.busy=False;self.analyze_btn.state(['!disabled']);self.export_btn.state(['!disabled']);self.progress.stop()

    def refresh(self):
        r=self.result;sc=r['scores'];self.cards['fish'].configure(text=len(sc));self.cards['points'].configure(text=f"{r['rows']:,}");self.cards['scorable'].configure(text=f'{sc.score.notna().sum()} / {len(sc)}')
        self.scoretree.delete(*self.scoretree.get_children())
        for row in sc.itertuples():self.scoretree.insert('', 'end',iid=str(row.fish_id),values=(row.fish_id,fmt(row.score),row.label,f'{row.available_metrics} / 58',row.scored_metrics,f'{row.available_weight_pct:.0f}',row.score_status),tags=('warning',) if not finite(row.score) else ())
        self.fishbox.configure(values=r['fish_ids']);self.fishvar.set(r['fish_ids'][0]);self.refresh_details();self.draw_plot()
        self.draw_gauge(float(sc.score.mean()) if sc.score.notna().any() else None)
        self.summary.configure(text=f"{r['score_title']} · 人工初始权重\n轨迹推进时间：{r['span_s']:.2f} 秒\n采样率：{1/r['frame_dt_s']:.2f} Hz\n平均分仅含质量门槛通过的个体。")

    def refresh_details(self):
        self.detailtree.delete(*self.detailtree.get_children())
        if not self.result:return
        d=self.result['details'];d=d[d.fish_id==self.fishvar.get()]
        for row in d.itertuples():
            mode=self.filtervar.get()
            if mode=='有数值' and not finite(row.value):continue
            if mode=='缺少条件' and finite(row.value):continue
            if mode=='参与评分' and row.weight<=0:continue
            self.detailtree.insert('','end',iid=str(row.metric_id),values=(f'{row.metric_id:02d}',row.name,fmt(row.value),row.unit,row.status,fmt(row.weight),fmt(row.subscore),row.reason or row.notes),tags=('missing',) if not finite(row.value) else ('warning',) if row.status!='已计算' else ())

    def select_fish(self,event=None):
        sel=self.scoretree.selection()
        if sel:self.fishvar.set(sel[0]);self.refresh_details()

    def show_metric(self,event=None):
        sel=self.detailtree.selection()
        if not sel:return
        mid=int(sel[0]);m=CATALOG['metrics'][mid-1];win=ctk.CTkToplevel(self);win.title(f'#{mid} {m["name"]}');win.geometry('820x650');win.configure(fg_color=BG)
        text=ctk.CTkTextbox(win,wrap='word',corner_radius=16,fg_color='white',text_color=INK,font=(FONT,15),spacing1=4,spacing3=8);text.pack(fill='both',expand=True,padx=18,pady=18)
        for label,key in [('指标','name'),('维度','dimension'),('实验情境','assay'),('操作定义','definition'),('解释方向','interpretation'),('注意事项','notes')]:text.insert('end',f'{label}\n{m[key] or "—"}\n\n')
        if self.result:
            row=self.result['details'];row=row[(row.fish_id==self.fishvar.get())&(row.metric_id==mid)].iloc[0]
            text.insert('end',f'本次计算\n{row.status}：{fmt(row.value)} {row.unit}\n{row.reason}\n{row.notes}\n来源：{row.source}')
        text.configure(state='disabled')

    def refresh_weights(self):
        self.weighttree.delete(*self.weighttree.get_children())
        for rule in self.cfg['scoring']['rules']:
            m=CATALOG['metrics'][rule['id']-1]
            self.weighttree.insert('','end',iid=str(rule['id']),values=(rule['id'],m['name'],fmt(rule['weight']),rule['direction'],fmt(rule['low']),fmt(rule['high']),'参与评分' if rule['weight'] else '仅描述 / 未启用'))

    def edit_weight(self):
        if self.busy:return
        sel=self.weighttree.selection()
        if not sel:messagebox.showinfo('选择指标','请先选择一条指标。');return
        mid=int(sel[0]);r=next(r for r in self.cfg['scoring']['rules'] if r['id']==mid)
        win=ctk.CTkToplevel(self);win.title(f'编辑 #{mid} 权重');win.geometry('580x470');win.configure(fg_color=BG);win.transient(self);win.grab_set()
        self.label(win,CATALOG['metrics'][mid-1]['name'],18,INK,True,wraplength=530).pack(anchor='w',padx=24,pady=(22,16))
        panel=ctk.CTkFrame(win,corner_radius=18,fg_color='white');panel.pack(fill='x',padx=20,pady=0)
        fields={}
        for key,label in [('weight','原始权重（0 为不参与评分）'),('low','数值下限'),('high','数值上限')]:
            f=ctk.CTkFrame(panel,fg_color='transparent');f.pack(fill='x',padx=18,pady=8);self.label(f,label,13).pack(side='left');v=tk.StringVar(value='' if r[key] is None else str(r[key]));ctk.CTkEntry(f,textvariable=v,width=170,height=36,corner_radius=10,border_color='#D6E2EC',fg_color='#F7FAFD',text_color=INK,font=(FONT,14)).pack(side='right');fields[key]=v
        direction=tk.StringVar(value=r['direction']);ctk.CTkComboBox(panel,variable=direction,values=['正向','反向'],state='readonly',height=36,corner_radius=10,font=(FONT,14)).pack(fill='x',padx=18,pady=(6,18))
        self.label(win,'上下限与指标使用相同单位。非活跃性指标启用后，\n评分名称改为“探索性综合行为分”。',13,MUTED,wraplength=530,justify='left').pack(anchor='w',padx=24,pady=12)
        def save():
            try:
                c=copy.deepcopy(self.cfg);rr=next(x for x in c['scoring']['rules'] if x['id']==mid)
                for k,v in fields.items():rr[k]=float(v.get()) if v.get().strip() else None
                rr['direction']=direction.get();validate_config(c);self.cfg=c;self.refresh_weights()
                if self.result:rescore(self.result,c);self.refresh()
                win.destroy()
            except Exception as e:messagebox.showerror('权重错误',str(e),parent=win)
        RoundButton(win,'保存并重新评分',save,primary=True).pack(fill='x',padx=24,pady=(4,18))

    def reset_weights(self):
        if self.busy:return
        self.cfg['scoring']=default_config()['scoring'];self.refresh_weights()
        if self.result:rescore(self.result,self.cfg);self.refresh()

    def load_scheme(self):
        if self.busy:return
        p=filedialog.askopenfilename(title='导入分析参数与权重 JSON',filetypes=[('JSON','*.json')])
        if not p:return
        try:self.set_config(json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig')));self.status.set('方案已导入，请重新点击开始分析。')
        except Exception as e:messagebox.showerror('方案无效',str(e))

    def save_scheme(self):
        try:c=self.get_config()
        except Exception as e:messagebox.showerror('参数错误',str(e));return
        p=filedialog.asksaveasfilename(title='保存方案',defaultextension='.json',initialfile='分析参数与权重.json')
        if p:pathlib.Path(p).write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')

    def advanced(self):
        if self.busy:return
        win=ctk.CTkToplevel(self);win.title('高级参数 · 质量门槛 · 输入单位');win.geometry('900x720');win.configure(fg_color=BG)
        self.label(win,'修改输入单位、计算参数或质量门槛后，请重新分析轨迹。',14,MUTED,wraplength=850).pack(anchor='w',padx=22,pady=18)
        txt=ctk.CTkTextbox(win,wrap='none',font=('Consolas',14),corner_radius=14,fg_color='white',text_color=INK);txt.pack(fill='both',expand=True,padx=20)
        data={k:v for k,v in self.get_config().items() if k!='scoring'};txt.insert('1.0',json.dumps(data,ensure_ascii=False,indent=2))
        def save():
            try:
                c=json.loads(txt.get('1.0','end'));c['scoring']=self.cfg['scoring'];self.set_config(c);win.destroy();self.status.set('参数已保存，请重新点击开始分析。')
            except Exception as e:messagebox.showerror('参数错误',str(e),parent=win)
        RoundButton(win,'保存参数',save,primary=True).pack(pady=16)

    def export(self):
        if self.busy:return
        if not self.result:messagebox.showinfo('尚无结果','请先完成一次分析。');return
        try:
            current=self.get_config()
            if any(current[k]!=self.result['config'][k] for k in ['engine','input','quality']):
                messagebox.showinfo('参数已改变','分析参数或质量门槛已改变，请重新点击“开始分析”再导出。');return
            if self.paths!=self.result['input_files'] and [str(pathlib.Path(p).resolve()) for p in self.paths]!=self.result['input_files']:
                messagebox.showinfo('文件已改变','已选择其他轨迹文件，请重新分析后导出。');return
            if (str(self.supplement) if self.supplement else None)!=self.result['supplement_file']:
                messagebox.showinfo('实验数据已改变','补充实验文件已改变，请重新分析后导出。');return
        except Exception as e:messagebox.showerror('参数错误',str(e));return
        base=filedialog.askdirectory(title='选择报告保存位置（自动新建本次报告文件夹）')
        if not base:return
        folder=pathlib.Path(base)/('鱼类分析_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        self.task(lambda:('export',export_all(self.result,folder,lambda s:self.bus.put(('status',s)))))

    def draw_gauge(self,value):
        self.gauge_value=value
        title=self.result['score_title'] if self.result else '探索性综合行为分'
        self.gauge_caption.configure(text=f'平均{title}')
        self.gauge_number.configure(text=f'{value:.1f}' if finite(value) else '—')
        self.gauge_bar.set(float(value)/100 if finite(value) else 0)

    def draw_plot(self):
        c=self.plot;c.delete('all');w=c.winfo_width();h=c.winfo_height()
        if not self.result or w<100:return
        d=self.result['trajectories'];colors=['#008b93','#6381dc','#d99542','#ab65ad','#439b67']
        for part,(xc,yc,title) in enumerate([('x_m','y_m','水平 X/Y（m）'),('x_m','z_m','侧视 X/Z（m）')]):
            left=35+part*w/2;right=(part+1)*w/2-25;top=40;bottom=h-35
            c.create_text(left,12,text=title,anchor='nw',fill=INK);c.create_rectangle(left,top,right,bottom,outline='#d7e3ea')
            xmin,xmax=float(d[xc].min()),float(d[xc].max());ymin,ymax=float(d[yc].min()),float(d[yc].max())
            for j,(fid,fish) in enumerate(d.groupby('fish_id')):
                if j>=30:break
                for _,s in fish.groupby('segment_id'):
                    if len(s)>500:s=s.iloc[__import__('numpy').linspace(0,len(s)-1,500).astype(int)]
                    pts=[]
                    for x,y in zip(s[xc],s[yc]):pts.extend([left+8+(x-xmin)/max(xmax-xmin,.001)*(right-left-16),bottom-8-(y-ymin)/max(ymax-ymin,.001)*(bottom-top-16)])
                    if len(pts)>=4:c.create_line(*pts,fill=colors[j%len(colors)],width=1)
            c.create_text(left,bottom+8,text=f'{xmin:.3f}',anchor='nw',fill=MUTED);c.create_text(right,bottom+8,text=f'{xmax:.3f}',anchor='ne',fill=MUTED)

    def close(self):
        if self.busy and not messagebox.askyesno('正在处理','关闭窗口将中止当前操作，是否关闭？'):return
        self.destroy()

HELP='''使用流程
1. 点击“导入轨迹 CSV”，可多选同一实验的分时文件。配置水槽半径、水深、体长及速度阈值。
2. 点击“开始分析”，在总览与指标页查看结果和缺失原因。
3. 在“权重与评分”页双击指标，可编辑 58 条权重、方向、数值上下限。
4. 点击“导出报告与 Excel”，生成独立 HTML 报告、Excel、CSV、参数与处理记录。HTML 可在浏览器打印为 PDF。

输入数据
标准字段：fish_id,timestamp_ms,x_m,y_m,z_m。建议另含 segment_id,point_type。
坐标单位默认米；X/Y 为水平面，Z 为离缸底高度。timestamp_s/time_s 可作秒时间列。
point_type 可为 observed、interpolated、predicted、dead。预测点默认排除。
仿真原始格式须含 physics_time_s；自动识别后将原 Y（向下为负）换算为离底高度，原 Z 作为水平 Y。
多个独立实验请提供 session_id，避免鱼编号被误当作连续身份。重复的鱼×时间记录会拒绝导入。

58 条指标的含义
系统包含58条指标，一条可能包含多个分量。自由游动轨迹可计算其中 33 条的代表值/变体；其余需要专门实验、刺激事件或人工标注。
补充实验 CSV 字段：fish_id,metric_id,value,unit,source,protocol。单位与定义须一致，source 和 protocol 必填。补充值可能覆盖轨迹代表值，并保留来源。

分数解释
默认启用31条运动、空间与社会指标。这些是可修改的工程初值，不是物种通用阈值。
单项分=100×clip((x−下限)/(上限−下限),0,1)，反向取100−单项分。
总分=Σ(可用权重×单项分)/Σ可用权重。综合行为分按低、中、高分展示，不能直接解释为活跃度；分级边界也需标定。
同一量的多个指标条目（如#13与#17）不宜重复加权。启用社会性、勇敢性或好斗性条目后，系统改称探索性综合行为分。

质量门槛
默认有效运动时长≥30 s、有效运动步≥20、跟踪覆盖率≥50%、跳点比例≤10%、可用评分权重≥70%，且无越界坐标，才显示总分。
研究建议有效跟踪时长初值300 s，短于该值标为谨慎使用。30 s评分门槛仅为演示性工程门槛，并不证明性格稳定。
缺失与不可用值不补零；不规则采样下的精细运动指标不计分。社会指标须同帧同步，超出内存保护上限会保留不可用原因。
独立重复实验与行为学验证仍需另行开展。
'''

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--analyze',nargs='+');ap.add_argument('--out');ap.add_argument('--config');ap.add_argument('--supplement');ap.add_argument('--smoke-gui');a=ap.parse_args()
    if a.analyze:
        try:
            cfg=json.loads(pathlib.Path(a.config).read_text(encoding='utf-8-sig')) if a.config else default_config()
            r=analyze(a.analyze,cfg,a.supplement);export_all(r,a.out or 'fish58_report')
        except BaseException:
            if a.out:
                pathlib.Path(a.out).mkdir(parents=True,exist_ok=True);pathlib.Path(a.out,'error.log').write_text(traceback.format_exc(),encoding='utf-8')
            return 1
        return
    app=App()
    if a.smoke_gui:
        out=pathlib.Path(a.smoke_gui);out.mkdir(parents=True,exist_ok=True)
        app.paths=[str(ASSETS/'examples'/'合成示例_三条鱼.csv')]
        def done(op,data):
            if op=='analysis':
                app.task(lambda:('export',export_all(app.result,out)))
            else:
                app.update_idletasks();(out/'gui_smoke_ok.json').write_text(json.dumps({'title':app.title(),'tabs':len(app.nb.tabs()),'fish':len(app.scoretree.get_children()),'metrics':len(app.detailtree.get_children()),'weights':len(app.weighttree.get_children()),'geometry':app.geometry()},ensure_ascii=False),encoding='utf-8')
                app.after(1000,app.destroy)
        app.after_job=done;app.after(700,app.start)
    app.mainloop()

if __name__=='__main__':sys.exit(main() or 0)

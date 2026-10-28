# 鱼类三维轨迹行为特征分析与质量评估

Windows 桌面应用，用于导入 CSV、检查轨迹质量、计算行为特征并导出报告。内置 58 条指标清单，默认有 31 项非零权重。程序展示每尾鱼实际参与评分的项目与可用权重。

文献支持指标定义和实验方法；默认权重、方向及上下限为未经实验标定的工程初值。综合行为分不能直接解释为纯活跃度或稳定性格。部分指标需要专门实验和额外标注，不能仅从自由游动轨迹计算。详见“31项权重与文献依据.md”。

## 运行

建议使用 Windows x64 和 Python 3.10。

```powershell
python -m pip install -r requirements.txt
python app.py
```

在界面中点击“保存 CSV 模板”获得字段示例；合成示例数据仅用于测试。标准输入需包含 fish_id、timestamp_ms、x_m、y_m、z_m。

## 测试与打包

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -p test_analysis.py -v
./build.ps1
```

EXE 打包使用 PyInstaller；图形界面使用 CustomTkinter。报告、原始轨迹和生成的 EXE 不包含在此源码仓库中。

## 权重与出处

权重可在程序内编辑及保存为 JSON。条目引用、数值上下限和方向详见“58项指标权重初始方案.csv”和“31项权重与文献依据.md”。

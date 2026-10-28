# Fish Trajectory Behavior Analysis

Windows desktop application for 3D fish trajectory analysis and quality checks. Import CSV trajectories, review 58 indicators, adjust the 31-item exploratory weighting scheme, and export analysis reports. The composite score is experimental and requires calibration for the species and recording setup.

## Run

Requires Windows x64 and Python 3.10.

```powershell
python -m pip install -r requirements.txt
python app.py
```

Required CSV columns: `fish_id`, `timestamp_ms`, `x_m`, `y_m`, `z_m`. Sample templates can be saved from the application.

## Test and build

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -p test_analysis.py -v
./build.ps1
```

The Windows executable is available in Releases.

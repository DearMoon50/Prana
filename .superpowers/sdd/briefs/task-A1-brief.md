### Task A1: Create `prana/` package and add packaging config

**Files:**
- Create: `prana/__init__.py`
- Create: `pyproject.toml`
- Modify (git mv): the 9 root modules → `prana/`

**Interfaces:**
- Produces: importable package `prana` exposing `prana.config`, `prana.prana_system`, `prana.ccri_calculator`, `prana.ha_aqi_calculator`, `prana.ndt_calculator`, `prana.rds_calculator`, `prana.data_fetcher`, `prana.uhi_lookup`, `prana.location_detector`. Also keeps `backend` importable as a top-level package.

- [ ] **Step 1: Move the 9 modules into the package with git mv**

```bash
cd "/c/Users/gokul D/prana"
mkdir prana
git mv config.py ccri_calculator.py ha_aqi_calculator.py ndt_calculator.py \
       rds_calculator.py data_fetcher.py uhi_lookup.py location_detector.py \
       prana_system.py prana/
```

- [ ] **Step 2: Create `prana/__init__.py`**

```python
"""PRANA climate-risk formula engine package."""
```

- [ ] **Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "prana"
version = "0.1.0"
description = "PRANA compound climate-risk formula engine and backend."
requires-python = ">=3.9"
dependencies = [
    "numpy>=1.26.0",
    "pandas>=2.0.3",
    "requests>=2.31.0",
    "geopy>=2.4.0",
    "python-dotenv>=1.0.0",
    "fastapi>=0.111.0",
    "uvicorn[standard]>=0.30.1",
]

[project.optional-dependencies]
research = [
    "statsmodels>=0.14.0",
    "pyarrow>=14.0.0",
    "scipy>=1.11.0",
]
dev = ["pytest>=7.4.0"]

[tool.setuptools]
packages = ["prana", "backend"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Commit the move (imports still broken — that's expected, fixed next task)**

```bash
git add -A
git commit -m "refactor: move formula engine into prana/ package (imports fixed next)"
```

---


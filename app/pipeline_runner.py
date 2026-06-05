import importlib.util
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List


ROOT = Path(__file__).resolve().parents[1]


MODULES = [
    ("app.driver_diagnosis", True),
    ("app.export_oil_profile_diagnostics", False),
    ("app.export_bhp_profile_diagnostics", False),
    ("app.export_gas_profile_diagnostics", False),
    ("app.injection_history_match", False),
    ("app.streamline_cluster_snap_mapper", False),
    ("app.producer_injector_context", False),
    ("app.final_hm_interpreter", True),
    ("app.final_gas_interpreter", False),
    ("app.final_oil_interpreter", False),
    ("app.porosity_pressure_observations", False),
    ("app.plot_transmissibility_corridors", False),
]


def module_exists(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def run_pipeline() -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []
    started = time.time()

    for module_name, required in MODULES:
        if not module_exists(module_name):
            results.append({
                "module": module_name,
                "status": "skipped",
                "required": required,
                "message": "Module not found",
                "seconds": 0,
            })
            continue

        t0 = time.time()

        proc = subprocess.run(
            [sys.executable, "-m", module_name],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )

        elapsed = round(time.time() - t0, 2)

        status = "success" if proc.returncode == 0 else "failed"

        results.append({
            "module": module_name,
            "status": status,
            "required": required,
            "seconds": elapsed,
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        })

        if required and proc.returncode != 0:
            return {
                "status": "failed",
                "failed_module": module_name,
                "seconds": round(time.time() - started, 2),
                "steps": results,
            }

    return {
        "status": "success",
        "seconds": round(time.time() - started, 2),
        "steps": results,
    }


if __name__ == "__main__":
    payload = run_pipeline()
    print(payload)

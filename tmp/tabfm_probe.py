import sys, time, json
sys.path.insert(0, "server")
from arcnet_server.tabfm_worker import forecast
import math
def series(n=40):
    return [10.0 + 2.0*math.sin(i/3.0) for i in range(n)]
t = time.time()
out = forecast(series(40), backend="tabfm")
dt = time.time() - t
res = {
  "elapsed_s": round(dt, 1),
  "status": out.get("status"),
  "estimator": out.get("estimator"),
  "n_predictions": len(out.get("predictions") or []),
  "first_preds": (out.get("predictions") or [])[:3],
  "detail_keys": list((out.get("detail") or {}).keys())[:8],
  "detail_error": (out.get("detail") or {}).get("error"),
}
print(json.dumps(res, indent=2), flush=True)

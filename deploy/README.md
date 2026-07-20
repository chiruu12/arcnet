# deploy/

SigNoz self-host via **Foundry** (required as of SigNoz ≥ v0.130; legacy `install.sh` retired).

| File | Purpose |
|---|---|
| `casting.yaml` | Foundry install spec — **pins `signoz/signoz:v0.133.0`** |
| `casting.yaml.lock` | Generated lock from `foundryctl` |
| `docker-compose.yaml` | Symlink → `pours/deployment/compose.yaml` (generated) |
| `pours/` | Foundry-generated Compose + configs (gitignored contents OK to regenerate) |
| `provision/agno-dashboard.json` | Official Agno dashboard template (import in UI / Phase 2 script) |
| `mcp/` | SigNoz MCP client configs (Phase 2) |

```bash
# needs foundryctl on PATH (darwin_arm64 binary from SigNoz/foundry releases)
foundryctl cast -f casting.yaml
# UI http://localhost:8080 · OTLP :4317/:4318
```

**Manual:** create a service-account API key in the SigNoz UI (Settings → Service Accounts) and set `SIGNOZ_API_KEY` in `.env`. Not creatable headlessly.

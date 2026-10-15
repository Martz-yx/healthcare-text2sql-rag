# LLM Infrastructure

Self-hosted vLLM instances for the HIS Text-to-SQL system.

## Servers

| Server | GPU | Model | Compose file |
|--------|-----|-------|--------------|
| Big Brain | NVIDIA H100 (80 GB) | `RedHatAI/gemma-4-31B-it-FP8-block` (31B, FP8) | `docker-compose.big-brain.yaml` |
| Small Brain | NVIDIA RTX A4500 (20 GB) | `Vishva007/gemma-4-E4B-it-W4A16-AutoRound-GPTQ` (4.5B effective, INT4) | `docker-compose.small-brain.yaml` |

## Prerequisites

- Docker with a remote context configured for each GPU server
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) installed on each server
- Verify GPU access: `docker --context <ctx> run --rm --gpus all nvidia/cuda:12.3.0-base-ubuntu22.04 nvidia-smi`

## Setup

**1. Configure API keys:**
```bash
cp .env.example .env
# Edit .env with real API keys
```

**2. Deploy Big Brain (H100):**
```bash
docker --context <h100-context> compose -f docker-compose.big-brain.yaml --env-file .env up -d
```

**3. Deploy Small Brain (A4500):**
```bash
docker --context <a4500-context> compose -f docker-compose.small-brain.yaml --env-file .env up -d
```

First startup pulls the model from HuggingFace — this can take several minutes depending on bandwidth.

**4. Check logs:**
```bash
docker --context <h100-context> logs -f vllm_big_brain
docker --context <a4500-context> logs -f vllm_small_brain
```

Wait for `Uvicorn running on http://0.0.0.0:8000` before sending requests.

**5. Verify:**
```bash
curl -H "Authorization: Bearer <your-api-key>" http://<h100-ip>:8000/v1/models
curl -H "Authorization: Bearer <your-api-key>" http://<a4500-ip>:8000/v1/models
```

## Configuration

API keys are the only required config. Everything else (model, context length, GPU utilization) is set in the compose files.

| Variable | Used by | Description |
|----------|---------|-------------|
| `VLLM_BIG_BRAIN_API_KEY` | `docker-compose.big-brain.yaml` | Bearer token for the H100 instance |
| `VLLM_SMALL_BRAIN_API_KEY` | `docker-compose.small-brain.yaml` | Bearer token for the A4500 instance |

## Updating

To change model or vLLM version, edit the compose file and recreate:
```bash
docker --context <ctx> compose -f <compose-file> --env-file .env up -d
```

## Troubleshooting

- **`unknown or invalid runtime name: nvidia`** — Install the NVIDIA Container Toolkit and run `sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker`
- **Container keeps restarting** — Check logs for OOM or model loading errors. The `start_period` in the healthcheck gives time for model download.
- **Model disappears / service stops** — The `restart: always` policy handles crashes. For OOM, reduce `--max-model-len` or `--gpu-memory-utilization`.

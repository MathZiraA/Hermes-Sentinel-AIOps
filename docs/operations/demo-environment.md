# Ambiente de demonstração: Hermes no VPS ↔ cluster no notebook

Esta é a topologia usada na demonstração. O Hermes Agent roda 24/7 num VPS; o cluster e o Sentinel rodam num notebook
atrás de NAT. O motivo de cada escolha está no [ADR 0004](../architecture/adr/0004-hermes-via-mcp-e-tunel.md).

```
 Notebook                                               VPS
┌──────────────────────────────────────┐   HTTPS   ┌───────────────────────────────┐
│ Backend :8000 ───────────────────────┼──────────▶│ Hermes Agent (gateway /v1)    │
│ MCP 127.0.0.1:8765 ◀─────────────────┼── ssh -R ─┼── 10.250.250.1:18765          │
│ kind · Hermes Brain                  │           │   (só o container do Hermes)  │
└──────────────────────────────────────┘           └───────────────────────────────┘
```

Valores entre `<…>` são da sua instalação. Nunca coloque IPs, usuários ou tokens reais neste repositório.

## 1. Túnel SSH reverso (notebook → VPS)

**No VPS**, crie um usuário sem shell, só para o túnel:

```bash
useradd --system --create-home --home-dir /var/lib/sentinel-tunnel --shell /usr/sbin/nologin sentinel-tunnel
```

Em `/var/lib/sentinel-tunnel/.ssh/authorized_keys`, a chave só pode abrir aquela porta:

```
restrict,port-forwarding,permitlisten="<ip-bridge>:18765",command="/bin/false" ssh-ed25519 AAAA… sentinel-tunnel
```

E em `/etc/ssh/sshd_config.d/70-sentinel-tunnel.conf`:

```
Match User sentinel-tunnel
    AllowTcpForwarding remote
    GatewayPorts clientspecified
    PermitListen <ip-bridge>:18765
    PermitOpen none
    AllowAgentForwarding no
    X11Forwarding no
    PermitTTY no
    PasswordAuthentication no
    ClientAliveInterval 30
    ClientAliveCountMax 3
```

Valide com `sshd -t` e confira que o root não mudou (`sshd -T -C user=root`). Libere a porta só para o container do Hermes:

```bash
ufw allow in on <interface-bridge> from <ip-container-hermes> to <ip-bridge> port 18765 proto tcp
```

**No notebook**, gere uma chave própria (`ssh-keygen -t ed25519 -f ~/.ssh/sentinel_tunnel -N ""`) e crie
`~/.config/systemd/user/sentinel-tunnel.service`:

```ini
[Unit]
Description=Hermes Sentinel: túnel reverso do MCP para o VPS
After=network-online.target

[Service]
ExecStart=/usr/bin/ssh -N -T -i %h/.ssh/sentinel_tunnel -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -o StrictHostKeyChecking=yes -o BatchMode=yes \
  -R <ip-bridge>:18765:127.0.0.1:8765 sentinel-tunnel@<seu-vps>
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now sentinel-tunnel
systemctl --user status sentinel-tunnel
```

## 2. Hermes: servidor MCP e bots

No `config.yaml` do Hermes:

```yaml
mcp_servers:
  sentinel:
    url: http://<ip-bridge>:18765/mcp
    headers:
      Authorization: Bearer ${SENTINEL_MCP_TOKEN}
    timeout: 60
    connect_timeout: 20
    keepalive_interval: 60
```

O token fica no `.env` do Hermes, nunca no YAML. Teste com `hermes mcp test sentinel`.

### Os 5 bots (profiles)

```bash
for p in monitor supervisor investigator executor itsm; do
  hermes profile create "$p" --clone --description "Hermes Sentinel: $p"
done
```

Para cada bot:

- `profiles/<bot>/SOUL.md` define a personalidade e o papel;
- `profiles/<bot>/.env` recebe o token do bot (`SENTINEL_MCP_TOKEN=<token-do-bot>`, o mesmo de `SENTINEL_MCP_ROLE_TOKENS`);
- `profiles/<bot>/config.yaml` ganha a lista de ferramentas do papel:

```yaml
    tools:
      include: [cluster_status, listar_pods, visao_geral, memoria_buscar, memoria_ler, memoria_registrar]
```

As listas de cada papel estão em [docs/api](../api/README.md#servidor-mcp). Com `gateway.multiplex_profiles: true`, um
único processo atende todos os bots, e eles aparecem no Hermes Desktop.

## 3. Injetar falhas de verdade

O repositório de teste (`stockflow-kubernetes/local`) traz cenários de caos:

| Comando | Falha |
|---|---|
| `chaos.sh oom` | OOMKilled (processo filho morto pelo kernel) |
| `chaos.sh crash` | CrashLoopBackOff |
| `chaos.sh imagepull` | ImagePullBackOff |
| `chaos.sh config` | CreateContainerConfigError (ConfigMap inexistente) |
| `chaos.sh pending` | FailedScheduling (pede CPU demais) |
| `chaos.sh job` | JobFailed |
| `chaos.sh pvc` | PVCPending (StorageClass inexistente) |
| `chaos.sh reset` | remove tudo |

## Operação do dia a dia

| Situação | O que acontece / o que fazer |
|---|---|
| Notebook desligado | O Hermes segue no ar e avisa que não alcança o cluster |
| Túnel caiu | O systemd reconecta em 10 s; enquanto isso o Sentinel usa o fallback |
| Gateway 502 logo após reiniciar o Hermes | Ele ainda está subindo; aguarde ~30 s |
| Gemini 429/503 | O Hermes tenta de novo; o Sentinel respeita a cota e cai para o fallback se precisar |

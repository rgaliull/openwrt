# openwrt-vpn

Ansible playbook для развёртывания VPN-стека на роутерах OpenWrt: маршрутизация трафика через прокси + DPI-обход + защищённый удалённый доступ.

## Зачем

Российские провайдеры блокируют сайты и сервисы. Этот плейбук решает три задачи:

1. **Маршрутизация** (podkop + sing-box-extended) — проброс нужных ресурсов через VLESS/XHTTP/Reality прокси по community-спискам (Telegram, Meta, Discord) и пользовательским доменам
2. **DPI-обход** (zapret + nfqws) — обход глубокой инспекции пакетов для YouTube, Google, Discord через стратегию fake+multisplit
3. **Удалённый доступ** (tailscale-lite) — вход на роутер извне без белого IP

## Что ставится

| Компонент | Источник | Для чего |
|---|---|---|
| **podkop** | [itdoginfo/podkop](https://github.com/itdoginfo/podkop) | DNS-маршрутизация, community-списки, управление sing-box |
| **sing-box-extended** | [shtorm-7](https://github.com/shtorm-7/sing-box-extended) | Ядро прокси с XHTTP-транспортом |
| **zapret** | [remittor/zapret-openwrt](https://github.com/remittor/zapret-openwrt) | DPI-обход через nfqws |
| **tailscale-lite** | [routerich](https://github.com/routerich) | Облегчённый Tailscale (5 MB вместо 24 MB) |
| **podkop-xhttp-patch** | [moix89](https://github.com/moix89/podkop-xhttp-patch) | Патч podkop для поддержки XHTTP |

Все пакеты зеркалированы в [rgaliull/openwrt](https://github.com/rgaliull/openwrt) для надёжности и скорости.

## Поддерживаемые платформы

- OpenWrt 24.10+ (opkg) и 25.12+ (apk)
- Архитектура aarch64_cortex-a53 (NanoPi R5S, Xiaomi AX3000T и др.)
- Для других архитектур нужны соответствующие пакеты в репозитории

## Требования к роутеру

| Параметр | Минимум | Рекомендация |
|---|---|---|
| RAM | 256 MB | 512 MB+ |
| Flash (overlay) | 60 MB | 128 MB+ |
| OpenWrt | 24.10+ | 25.12+ |
| Доступ | SSH (root) | Tailscale |

## Порядок установки

Плейбук выполняется в строгом порядке:

1. **pkg-check** — определение apk/opkg, установка zram-swap (сжатый swap в RAM, критически важно для роутеров с 256 MB)
2. **zapret** — DPI-обход: apk из zip с GitHub, opkg из feed, конфиг nfqws + hostlist'ы
3. **cleanup** — остановка сервисов, удаление старых пакетов, чистка бэкапов и кэша
4. **tailscale** — замена официального tailscaled (22 MB) на облегчённый tailscale-lite (5 MB), установка kmod-tun, GOGC=10, luci-i18n-ru
5. **sing-box-extended** — замена stock sing-box на extended: apk через install.sh, opkg — сжатый бинарник (15 MB, zram-safe)
6. **podkop** — установка с --nodeps (sing-box уже есть), UCI-конфигурация из group_vars
7. **patch** — xhttp-патч для podkop

## Решения для слабых роутеров (256 MB RAM)

На роутерах с ограниченной памятью применяется комплекс мер:

| Мера | Экономия |
|---|---|
| **zram-swap** (zstd) | +250-350 MB эффективной памяти |
| **tailscale-lite** 5 MB | -17 MB на флешке, -30 MB RSS |
| **GOGC=10** для tailscale | -5-10 MB RAM (агрессивный GC) |
| **sing-box сжатый (UPX)** | -50 MB на флешке, zram страхует RAM |
| **zapret stop** на время установки | -20 MB RAM пиково |
| **drop_caches** между этапами | освобождение буферов |
| **Python не требуется** | -10 MB RAM (все задачи через raw) |

## Структура проекта

```
openwrt-vpn/
├── ansible.cfg              # transfer_method=scp, scp_extra_args=-O
├── playbook.yml             # порядок ролей + post_tasks
├── inventory/hosts.yml      # роутеры (приватный, не в репо!)
├── group_vars/all.yml       # DNS, zapret, community lists, домены
├── filter_plugins/
│   └── vless_parser.py      # конвертер vless:// → sing-box outbound JSON
└── roles/
    ├── pkg-check/            # apk/opkg + zram-swap
    ├── zapret/               # установка + конфиг + hostlist'ы + UCI
    ├── cleanup/              # остановка, удаление, чистка
    ├── tailscale/            # замена бинарника + luci-i18n + GOGC
    ├── sing-box-extended/    # apk: install.sh / opkg: compressed tar.gz
    ├── podkop/               # --nodeps + UCI (coreutils-base64 для opkg)
    └── patch/                # xhttp-транспорт + фикс версии
```

## Быстрый старт

1. Клонируй репозиторий:
```sh
git clone https://github.com/rgaliull/openwrt.git
cd openwrt/playbook
```

2. Создай инвентори (`inventory/hosts.yml`) из шаблона:
```sh
cp inventory/hosts.example.yml inventory/hosts.yml
# заполни IP, пароль и vless-ссылку своего роутера
```

3. Запусти:
```sh
ansible-playbook playbook.yml
```

## Использование

```sh
# Все роутеры
ansible-playbook playbook.yml

# Конкретный роутер
ansible-playbook playbook.yml -l router-name

# Только определённая роль
ansible-playbook playbook.yml -t zapret
ansible-playbook playbook.yml -t tailscale
ansible-playbook playbook.yml -t podkop

# Пропустить роль
ansible-playbook playbook.yml --skip-tags sing-box-extended
```

## Настройка

Параметры в `group_vars/all.yml`:

| Переменная | Описание |
|---|---|
| `podkop_settings` | DNS (DoT через 8.8.8.8), интерфейсы, интервал обновления |
| `podkop_section_main.community_lists` | Списки: telegram, meta, hodca, geoblock |
| `podkop_section_main.user_domains_text` | Пользовательские домены через прокси |
| `zapret_config` | Порты nfqws, autohostlist, метки файрвола |
| `zapret_nfqws_strategy` | Стратегия DPI-обхода: fake+multisplit для TCP/443 |

## Community lists

| Список | Что маршрутизирует |
|---|---|
| `telegram` | Telegram |
| `meta` | Facebook, Instagram, WhatsApp, Threads |
| `hodca` | Discord |
| `geoblock` | Гео-ограничения |

## Как добавить роутер

В `inventory/hosts.yml`:

```yaml
router-name:
  ansible_host: 192.168.1.1
  ansible_user: root
  ansible_password: password
  ansible_connection: ssh
  ansible_shell_type: sh
  ansible_python_interpreter: /usr/bin/python3   # убрать для экономии RAM
  ansible_ssh_common_args: '-o ControlMaster=no'  # для Dropbear
  vless_link: "vless://uuid@server:443?...type=xhttp&security=reality&#tag"
```

## VLESS-ссылка

Формат: `vless://uuid@server:port?params#tag`

Конвертируется в sing-box outbound JSON через `filter_plugins/vless_parser.py`. Поддерживаются параметры:
- `type=xhttp`, `path`, `mode`, `host`, `sni`
- `security=reality`, `pbk`, `sid`, `fp`
- `x_padding_bytes`, `extra` (scMaxEachPostBytes и др.)

## Баги и особенности

- **Dropbear SSH**: не поддерживает ControlMaster. Решение: `ansible_ssh_common_args: '-o ControlMaster=no'` + `scp_extra_args: -O`
- **opkg без --nodeps**: тянет stock sing-box. Решение: ставим sing-box-extended отдельно, podkop — с `--nodeps`
- **coreutils-base64**: нужен podkop'у. На opkg ставится явно перед podkop
- **UPX OOM**: сжатый sing-box распаковывается в RAM целиком. Решение: zram-swap даёт буфер
- **UBIFS overlay 60 MB**: несжатый sing-box (65 MB) физически не влезает. Решение: сжатый бинарник (15 MB)

## Автор

Ramil Galiullin, 2026

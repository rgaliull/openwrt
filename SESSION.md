# openwrt-vpn — контекст сессии

## Проект
Ansible playbook для развёртывания podkop + sing-box-extended + zapret + tailscale-lite на роутерах OpenWrt.

## Репозиторий
- **Пакеты и плейбук**: https://github.com/rgaliull/openwrt
- **Деплой-ключ**: `deploy_key` (приватный, в `.gitignore`)
- Все внешние зависимости зеркалированы в `aarch64_cortex-a53/` и `all/`

## Роутеры в инвентори

| Имя | IP | Модель | OpenWrt | PKG | RAM | Статус |
|---|---|---|---|---|---|---|
| router-reutov | 192.168.199.1 | NanoPi R5S | 25.12.0 | apk | 4 GB | ✅ рабочий |
| bulat | 100.125.132.53 | Xiaomi AX3000T | 24.10.2 | opkg | 256 MB | 🛑 ждёт прокатки |
| almet | 100.66.210.72 | — | 24.10.2 | opkg | 256 MB | ✅ рабочий |

## Состояние на bulat (проблема)
- **Причина OOM**: UPX-compressed sing-box-extended при запуске декомпрессится в память целиком + Go-рантайм ~120 MB + tmpfs /tmp = OOM на 256 MB
- **Решение (комплексное)**:
  1. zram-swap (~118 MB сжатого свопа в RAM)
  2. Не-compressed бинарник (65 MB на диске, UBIFS сожмёт, память по страницам)
  3. Стрим-распаковка: `wget -O- | tar -xz -C /root/` — архив не пишется в tmpfs
  4. Убран `ansible_python_interpreter` из инвентори (~10 MB экономия)
  5. zapret глушится в cleanup перед тяжёлой установкой (~20 MB)
  6. podkop ipk скачивается в `/root/`, не в `/tmp`
  7. tailscale-lite (5 MB вместо 24 MB) + GOGC=10
  8. coreutils-base64, bind-dig — ставятся перед podkop на opkg
  9. drop_caches между этапами

## Структура плейбука
```
openwrt-vpn/
├── ansible.cfg
├── playbook.yml          # pkg-check → zapret → cleanup → tailscale → sing-box-extended → podkop → patch
├── inventory/hosts.yml   # роутеры: IP, пароль, vless_link, ansible_ssh_common_args: '-o ControlMaster=no'
├── group_vars/all.yml    # DNS, zapret, community lists (telegram, meta, hodca, geoblock)
├── filter_plugins/vless_parser.py  # vless:// → sing-box outbound JSON
└── roles/
    ├── pkg-check/        # автоопределение apk/opkg + zram-swap
    ├── zapret/           # apk: zip с GitHub remittor → apk add / opkg: из feed
    ├── cleanup/          # стоп zapret+podkop, чистка старых пакетов, бэкапов, APK-кэша
    ├── tailscale/        # замена бинарника + luci-i18n + kmod-tun + GOGC=10
    ├── sing-box-extended/ # apk: official script / opkg: compressed tar.gz (UPX, zram-safe)
    ├── podkop/           # opkg: coreutils-base64+bind-dig + podkop --nodeps / apk: из apk
    └── patch/            # moix89/podkop-xhttp-patch (xhttp transport + version fix)
```

## Ключевые моменты
- **zram-swap**: первым делом в pkg-check — сжатый swap в RAM (zstd), флешку не трогает
- **tailscale**: заменяется на routerich tailscale-lite (5 MB) + luci-i18n-ru, ipk в `roles/tailscale/files/`
- **GOGC=10**: в init.d/tailscale для агрессивной сборки мусора
- **opkg роутеры**: sing-box-extended сжатый (UPX, 15 MB на диске), zram-swap страхует от OOM
- **podkop на opkg**: сначала coreutils-base64 и bind-dig, потом podkop `--nodeps`
- **zapret на apk**: качается zip с GitHub remittor, ставится apk напрямую, без внешнего репо
- **SCP/Dropbear**: `ansible_ssh_common_args: '-o ControlMaster=no'` + `scp_extra_args: -O`
- **Фейк opkg-пакет**: регистрируем sing-box в opkg status
- **community lists**: telegram, meta, hodca, geoblock
- **nfqws стратегия**: fake+multisplit для TCP/443 с google hostlist
- **DNS**: sing-box на 127.0.0.42:53, fakeip 198.18.0.0/15

## Баги, которые пофиксили
- `'INSTALLED' in 'NOT_INSTALLED'` → заменили на точное равенство `== 'INSTALLED'`
- YAML heredoc с `<< 'EOF'` ломает парсинг → заменили на `printf`
- `url.fragment[1:]` срезал `v` из `vless-...` → исправили на `url.fragment`
- Два register в одну переменную → перезапись skipped-результатом → одна задача на apk/opkg
- `--rdepends` каскадно сносит podkop+zapret → не использовать, удалять точечно

## Команды
```sh
cd ~/claude/openwrt/openwrt-vpn
ansible-playbook playbook.yml                # все роутеры
ansible-playbook playbook.yml -l bulat       # конкретный
ansible-playbook playbook.yml -t zapret      # только zapret
ansible-playbook playbook.yml -t tailscale   # только tailscale
ansible-playbook playbook.yml -t podkop      # только podkop
ansible-playbook playbook.yml -t sing-box-extended
ansible-playbook playbook.yml --skip-tags sing-box-extended
```

## Ручное восстановление после OOM на булате
```sh
# 1. LuCI: System → Startup → podkop Stop + Disabled → Reboot
# 2. После ребута tailscale поднимется, затем:
rm -f /usr/bin/sing-box
mkdir -p /root/sbx-extract
wget -qO- https://github.com/shtorm-7/sing-box-extended/releases/download/v1.13.12-extended-2.3.2/sing-box-1.13.12-extended-2.3.2-linux-arm64.tar.gz | tar -xzf - -C /root/sbx-extract
find /root/sbx-extract -name sing-box -type f -exec mv {} /usr/bin/sing-box \;
chmod +x /usr/bin/sing-box
rm -rf /root/sbx-extract
# 3. Запустить playbook с ноутбука
ansible-playbook playbook.yml -l bulat
```

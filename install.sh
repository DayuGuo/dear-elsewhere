#!/usr/bin/env bash
# Install Dear Elsewhere on a Debian/Ubuntu VPS using systemd.
set +x
set -euo pipefail
umask 022

fail() { printf '安装中止：%s\n' "$*" >&2; exit 1; }

replace_token=false
case "${1:-}" in
    --replace-token) replace_token=true ;;
    "") ;;
    *) fail "用法：sudo bash install.sh [--replace-token]" ;;
esac
[[ $# -le 1 ]] || fail "仅支持 --replace-token"
[[ $(uname -s) == Linux && -f /etc/debian_version && -d /run/systemd/system ]] ||
    fail "需要使用 systemd 的 Debian / Ubuntu VPS。"
[[ $EUID -eq 0 ]] || fail "请使用 sudo bash 运行此脚本。"
exec 9>/run/lock/dear-elsewhere-install.lock
flock -n 9 || fail "已有安装进程正在运行。"

app=/opt/dear-elsewhere
config=/etc/dear-elsewhere.env
web=dear-elsewhere.service
timer=dear-elsewhere-sync.timer
sync=dear-elsewhere-sync.service
site=http://127.0.0.1:8791/
work=$(mktemp -d)
pending_config=
cleanup() {
    rm -rf -- "$work"
    if [[ -n $pending_config ]]; then rm -f -- "$pending_config"; fi
}
trap cleanup EXIT

echo '正在安装依赖并下载 Dear Elsewhere…'
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates curl git iproute2 python3 python3-venv
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' ||
    fail "需要 Python 3.11 或以上版本，建议使用 Debian 12+ 或 Ubuntu 24.04+。"
git clone --quiet --depth 1 --branch main https://github.com/DayuGuo/dear-elsewhere.git "$work/source"
cd "$work/source"

default_domain=dearelsewhere.anotherdayu.com
if [[ -s /etc/dear-elsewhere.domain ]]; then
    read -r default_domain < /etc/dear-elsewhere.domain
fi
printf '公网域名 [%s]（回车接受，输入 - 跳过 HTTPS 配置）：' "$default_domain" >/dev/tty
IFS= read -r domain </dev/tty || fail "请在交互式 SSH 终端中运行。"
domain=$(printf '%s' "${domain:-$default_domain}" | LC_ALL=C tr 'A-Z' 'a-z')
label='[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?'
if [[ $domain != - ]]; then
    [[ ${#domain} -le 253 && $domain =~ ^(${label}\.)+[a-z]{2,63}$ ]] ||
        fail "请输入完整的公网域名，例如 dearelsewhere.anotherdayu.com。"
fi

# Only systemd reads this file. Never source it or pass the token to a child process.
template=.env.example
if [[ -f $config ]]; then
    chown root:root "$config"
    chmod 0600 "$config"
    template=$config
fi
if "$replace_token" || ! awk '
    /^X_BEARER_TOKEN=/ {v=substr($0,16)}
    END {gsub(/[[:space:]"\047]/, "", v); exit !length(v)}
' "$template"; then
    printf '请粘贴 X 应用的 Bearer Token 并按回车（输入隐藏）：' >/dev/tty
    IFS= read -rs token </dev/tty || fail "需要交互式 SSH 终端来输入 Token。"
    printf '\n' >/dev/tty
    [[ $token =~ ^[a-zA-Z0-9._~+/%=-]+$ ]] || fail "Token 为空或包含无效字符，请重新运行并粘贴完整的 Bearer Token。"
    pending_config=$(mktemp /etc/.dear-elsewhere.env.XXXXXXXX)
    awk '!/^X_BEARER_TOKEN=/' "$template" > "$pending_config"
    printf 'X_BEARER_TOKEN=%s\n' "$token" >> "$pending_config"
    unset token
fi

if ! getent passwd dear-elsewhere >/dev/null; then
    useradd --system --user-group --home-dir /var/lib/dear-elsewhere --no-create-home --shell /usr/sbin/nologin dear-elsewhere
fi
install -d -o dear-elsewhere -g dear-elsewhere -m 0700 /var/lib/dear-elsewhere
install -d -m 0755 "$app"
if [[ ! -x $app/.venv/bin/python ]]; then python3 -m venv "$app/.venv"; fi
"$app/.venv/bin/python" -m pip install --disable-pip-version-check -r requirements.txt
git archive HEAD elsewhere requirements.txt | tar -x -C "$app"
install -m 0644 "deploy/$web" "deploy/$timer" "deploy/$sync" /etc/systemd/system/
if [[ -n $pending_config ]]; then
    mv -f -- "$pending_config" "$config"
    pending_config=
fi

systemctl daemon-reload
systemctl enable "$web"
systemctl restart "$web"
ready=false
for ((attempt=0; attempt<20; attempt++)); do
    if curl -fsS --max-time 2 "$site" -o "$work/home" 2>/dev/null && grep -q 'Dear Elsewhere' "$work/home"; then
        ready=true
        break
    fi
    sleep 1
done
"$ready" && systemctl is-active --quiet "$web" || fail "首页未通过检查。请运行 sudo journalctl -u $web -n 40"
echo "首页已就绪：$site"

systemctl enable --now "$timer"
systemctl is-active --quiet "$timer" || fail "定时器未启动，请运行 systemctl status $timer"
systemctl list-timers --all "$timer" --no-pager
result=0
echo '正在执行一次 X 标签同步…'
if ! systemctl start "$sync"; then
    echo "本次同步失败，每小时定时器已启用。查看 sudo journalctl -u $sync -n 40；更换 Token 可用 --replace-token。" >&2
    result=1
fi
if [[ $domain != - ]]; then
    if bash deploy/https.sh "$domain"; then
        printf '%s\n' "$domain" > /etc/dear-elsewhere.domain
        echo "网站已通过 HTTPS 检查：https://$domain/"
    else
        echo "HTTPS 尚未就绪。本机网站和定时器已启动；修正提示的问题后重新运行安装命令。" >&2
        result=1
    fi
fi
exit "$result"

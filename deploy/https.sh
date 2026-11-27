#!/usr/bin/env bash
# Called by install.sh with a normalized, validated domain name.
set -euo pipefail
domain=${1:?missing domain}
url=https://$domain/
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
fail() { printf '%s\n' "$*" >&2; exit 1; }

getent ahosts "$domain" >/dev/null || fail "VPS 无法解析 ${domain}。请添加指向本机公网地址的 A 或 AAAA 记录，等待 DNS 生效。"

# Respect an existing web server. Install Caddy only when the public ports are free.
listeners=$(ss -Hltnp '( sport = :80 or sport = :443 )')
if systemctl is-active --quiet caddy && systemctl is-active --quiet nginx; then
    fail "Caddy 和 Nginx 均已运行。请在负责该域名的代理中将 $domain 转发至 127.0.0.1:8791。"
elif systemctl is-active --quiet caddy; then
    proxy=caddy
elif systemctl is-active --quiet nginx; then
    proxy=nginx
elif [[ -n $listeners ]]; then
    fail "80 或 443 端口已有其他服务。请在现有代理上为 $domain 开启 HTTPS，上游为 127.0.0.1:8791。"
else
    proxy=caddy
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends caddy
fi

configure_caddy() {
    local config=/etc/caddy/Caddyfile
    local marker="# Dear Elsewhere: $domain"
    local candidate
    [[ -f $config ]] || fail "找不到 ${config}，请检查现有 Caddy 服务的配置路径。"
    [[ $(systemctl show caddy --property=ExecStart --value) == *"--config /etc/caddy/Caddyfile "* ]] ||
        fail "Caddy 使用自定义启动配置。请在当前配置中为 $domain 添加 reverse_proxy 127.0.0.1:8791。"
    config=$(readlink -f "$config")
    if ! grep -Fxq "$marker" "$config"; then
        # Keep the candidate next to the original so relative imports resolve correctly.
        candidate=$(mktemp "$(dirname "$config")/.dear-elsewhere.XXXXXXXX")
        cp --preserve=all "$config" "$candidate"
        printf '\n%s\n%s {\n\treverse_proxy 127.0.0.1:8791\n}\n' "$marker" "$domain" >> "$candidate"
        if ! caddy validate --adapter caddyfile --config "$candidate"; then
            rm -f -- "$candidate"
            fail "Caddy 配置验证失败，原配置已保留。请检查域名是否已配置。"
        fi
        cp --preserve=all "$config" "$work/original"
        mv -f -- "$candidate" "$config"
    fi
    if ! systemctl enable caddy || ! systemctl reload-or-restart caddy; then
        if [[ -f $work/original ]]; then cp --preserve=all "$work/original" "$config"; fi
        fail "Caddy 未能加载站点。请查看 journalctl -u caddy -n 40。"
    fi
}

configure_nginx() {
    local name="dear-elsewhere-$(printf '%s' "$domain" | sha256sum | cut -c1-16)"
    local file="/etc/nginx/conf.d/$name.conf" root=/var/www/dear-elsewhere-acme
    local cert="/etc/letsencrypt/live/$name" marker="# Dear Elsewhere: $domain"
    local ipv6=false
    [[ -s /proc/net/if_inet6 ]] && ipv6=true
    [[ -d /etc/nginx/conf.d ]] || fail "未找到 Nginx conf.d。请在现有代理中配置域名。"
    if [[ -e $file || -L $file ]]; then
        [[ -f $file && ! -L $file ]] && grep -Fxq "$marker" "$file" || fail "已有同名 Nginx 配置：$file"
        cp -p "$file" "$work/original"
    fi

    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends certbot
    install -d -m 0755 "$root"
    {
        echo "$marker"
        echo 'server {'
        echo '    listen 80;'
        if "$ipv6"; then echo '    listen [::]:80;'; fi
        echo "    server_name $domain;"
        echo "    location ^~ /.well-known/acme-challenge/ { root $root; }"
        echo "    location / { return 301 https://$domain\$request_uri; }"
        echo '}'
    } > "$work/http"
    {
        cat "$work/http"
        echo 'server {'
        echo '    listen 443 ssl;'
        if "$ipv6"; then echo '    listen [::]:443 ssl;'; fi
        echo "    server_name $domain;"
        echo "    ssl_certificate $cert/fullchain.pem;"
        echo "    ssl_certificate_key $cert/privkey.pem;"
        cat <<'NGINX'
    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_pass http://127.0.0.1:8791;
    }
}
NGINX
    } > "$work/https"

    # Verify the active configuration includes our file and accepts its hostname.
    load_site() {
        install -m 0644 "$1" "$file"
        if nginx -T > "$work/nginx" 2>"$work/errors" &&
           grep -Fxq "# configuration file $file:" "$work/nginx" &&
           ! grep -Fiq "conflicting server name \"$domain\"" "$work/errors" &&
           systemctl reload nginx; then return 0; fi
        if [[ -e $work/original ]]; then cp -p "$work/original" "$file"; else rm -f -- "$file"; fi
        nginx -t && systemctl reload nginx
        fail "Nginx 未能加载站点。请检查 conf.d 是否被包含、域名是否重复或监听端口是否冲突。"
    }
    if [[ -s $cert/fullchain.pem && -s $cert/privkey.pem ]]; then
        load_site "$work/https"
    else
        load_site "$work/http"
    fi
    certbot certonly --webroot -w "$root" -d "$domain" --cert-name "$name" --non-interactive \
        --agree-tos --register-unsafely-without-email --keep-until-expiring ||
        fail "证书申请失败。请检查公网 DNS、80 端口和 Certbot 日志，修正后重试。"
    # Re-read the certificate even if it was renewed at the same pathname.
    load_site "$work/https"
    install -d /etc/letsencrypt/renewal-hooks/deploy
    cat > "$work/reload-nginx" <<HOOK
#!/bin/sh
[ "\$RENEWED_LINEAGE" = "$cert" ] || exit 0
nginx -t && systemctl reload nginx
HOOK
    install -m 0755 "$work/reload-nginx" "/etc/letsencrypt/renewal-hooks/deploy/$name"
    systemctl enable nginx
    systemctl enable --now certbot.timer
}

"configure_$proxy"
echo "正在检查 $url 的有效证书和首页…"
for ((attempt=0; attempt<30; attempt++)); do
    if curl -fsS --max-time 4 --noproxy '*' --resolve "$domain:443:127.0.0.1" "$url" -o "$work/origin" 2>/dev/null &&
       grep -q 'Dear Elsewhere' "$work/origin" &&
       curl -fsS --max-time 5 "$url" -o "$work/page" 2>/dev/null &&
       grep -q 'Dear Elsewhere' "$work/page" &&
       [[ $(curl -s --max-time 4 -o /dev/null -w '%{redirect_url}' "http://$domain/") == "$url" ]]; then
        exit 0
    fi
    sleep 2
done
fail "尚未通过 HTTPS 首页检查。请确认 DNS 指向这台 VPS，公网可访问 TCP 80/443；检查 journalctl -u $proxy -n 40。"

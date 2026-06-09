import json
from urllib.parse import urlparse, parse_qs, unquote


def vless_to_outbound(vless_link):
    if not vless_link or not vless_link.startswith("vless://"):
        return "{}"

    url = urlparse(vless_link)
    params = parse_qs(url.query)

    uuid = url.username
    server = url.hostname
    port = int(url.port) if url.port else 443
    tag = unquote(url.fragment) if url.fragment else "VLESS-XHTTP"

    def p(key, default=None):
        v = params.get(key, [default] if default else [])
        return v[0] if v else default

    transport_type = p("type", "xhttp")
    path_val = p("path", "/")
    mode = p("mode", "auto")
    x_padding = p("x_padding_bytes", "100-1000")
    sni = p("sni", "")
    host = p("host") or sni
    security = p("security")
    is_reality = security == "reality"
    is_tls = security == "tls"
    pbk = p("pbk", "")
    sid = p("sid", "")
    fp = p("fp", "chrome")

    alpn_raw = p("alpn")
    if alpn_raw:
        alpn = unquote(alpn_raw).split(",")
    elif transport_type == "xhttp":
        alpn = ["h2", "http/1.1"]
    else:
        alpn = ["h2", "http/1.1"]

    tls_settings = {
        "enabled": True,
        "server_name": sni,
        "alpn": alpn,
    }

    if is_reality:
        tls_settings["reality"] = {
            "enabled": True,
            "public_key": pbk,
            "short_id": sid,
        }
        tls_settings["utls"] = {
            "enabled": True,
            "fingerprint": fp,
        }
    elif is_tls:
        if p("allowInsecure"):
            tls_settings["insecure"] = p("allowInsecure") == "1"
        if fp:
            tls_settings["utls"] = {
                "enabled": True,
                "fingerprint": fp,
            }

    transport_settings = {
        "type": transport_type,
        "path": path_val,
        "mode": mode,
        "x_padding_bytes": x_padding,
    }
    if host:
        transport_settings["host"] = host

    extra_raw = p("extra")
    if extra_raw:
        try:
            extra = json.loads(unquote(extra_raw))
            if extra.get("xPaddingBytes") is not None:
                transport_settings["x_padding_bytes"] = str(extra["xPaddingBytes"])
            if extra.get("scMaxEachPostBytes") is not None:
                transport_settings["sc_max_each_post_bytes"] = extra["scMaxEachPostBytes"]
            if extra.get("scMinPostsIntervalMs") is not None:
                transport_settings["sc_min_posts_interval_ms"] = extra["scMinPostsIntervalMs"]
            if extra.get("noGRPCHeader") is not None:
                transport_settings["no_grpc_header"] = extra["noGRPCHeader"]
            if extra.get("scStreamUpServerSecs") is not None:
                transport_settings["sc_stream_up_server_secs"] = str(extra["scStreamUpServerSecs"])
            if extra.get("seqKey") is not None:
                transport_settings["seq_key"] = extra["seqKey"]
            if extra.get("seqPlacement") is not None:
                transport_settings["seq_placement"] = extra["seqPlacement"]
            if extra.get("xPaddingKey") is not None:
                transport_settings["x_padding_key"] = extra["xPaddingKey"]
            if extra.get("xPaddingMethod") is not None:
                transport_settings["x_padding_method"] = extra["xPaddingMethod"]
            if extra.get("xPaddingObfsMode") is not None:
                transport_settings["x_padding_obfs_mode"] = extra["xPaddingObfsMode"]
            if extra.get("xPaddingPlacement") is not None:
                transport_settings["x_padding_placement"] = extra["xPaddingPlacement"]
            if extra.get("xmux") and isinstance(extra["xmux"], dict):
                xmux = {}
                xm = extra["xmux"]
                if xm.get("maxConcurrency") is not None:
                    xmux["max_concurrency"] = str(xm["maxConcurrency"])
                if xm.get("maxConnections") is not None:
                    xmux["max_connections"] = xm["maxConnections"]
                if xm.get("cMaxReuseTimes") is not None:
                    xmux["c_max_reuse_times"] = xm["cMaxReuseTimes"]
                if xm.get("hMaxRequestTimes") is not None:
                    xmux["h_max_request_times"] = str(xm["hMaxRequestTimes"])
                if xm.get("hMaxReusableSecs") is not None:
                    xmux["h_max_reusable_secs"] = str(xm["hMaxReusableSecs"])
                if xm.get("hKeepAlivePeriod") is not None:
                    xmux["h_keep_alive_period"] = xm["hKeepAlivePeriod"]
                if xmux:
                    transport_settings["xmux"] = xmux
        except (json.JSONDecodeError, TypeError):
            pass

    config = {
        "type": "vless",
        "tag": tag,
        "server": server,
        "server_port": port,
        "uuid": uuid,
        "tls": tls_settings,
        "transport": transport_settings,
    }

    return json.dumps(config, ensure_ascii=False, indent=2)


class FilterModule(object):
    def filters(self):
        return {"vless_to_outbound": vless_to_outbound}

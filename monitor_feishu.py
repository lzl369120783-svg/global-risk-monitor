import os
import sys
import datetime
import time
import hashlib
import hmac
import base64
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 修复 Windows 终端 GBK 编码问题
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# 确保能导入当前目录的已有模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import monitor_ashare as fa
import monitor_global as fg

# 从配置文件读取敏感信息（config.py 不提交 Git）
try:
    from config import FEISHU_WEBHOOK, FEISHU_SECRET
except ImportError:
    FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/YOUR_FEISHU_WEBHOOK"
    FEISHU_SECRET = "YOUR_FEISHU_SECRET"

def gen_sign(secret):
    """生成飞书机器人签名"""
    timestamp = str(int(time.time()))
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode("utf-8")
    return timestamp, sign

def push_to_feishu(md_content):
    """发送富文本卡片到飞书机器人（带签名校验）"""
    header = {"Content-Type": "application/json"}
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    
    timestamp, sign = gen_sign(FEISHU_SECRET)
    
    payload = {
        "msg_type": "interactive",
        "timestamp": timestamp,
        "sign": sign,
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 宏观金融监控日报 | {now_str}"
                },
                "template": "blue"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": md_content
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {"tag": "plain_text", "content": "上帝视角：A股与全球宏观风控自动生成"}
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(FEISHU_WEBHOOK, headers=header, json=payload, timeout=10)
        res_json = response.json()
        if res_json.get("code") == 0:
            print("💡 推送飞书成功!")
        else:
            print("❌ 推送飞书失败，错误信息:", res_json)
    except Exception as e:
        print("❌ 推送飞书发生网络错误:", str(e))

def fetch_cnbc_fast(symbol):
    try:
        return fg.fetch_cnbc(symbol)
    except:
        return None, None

def fetch_fred_fast(series_id):
    try:
        return fg.fetch_fred(series_id)
    except:
        return None, None

def generate_report():
    """调用数据引擎，生成 Markdown 格式的综合报告"""
    print(">>> 正在抓取 A股 数据 (AKShare)...")
    engine = fa.AKShareEngine()
    margin_val, _ = engine.get_latest_margin()
    mkt_metrics = engine.get_market_metrics()
    macro = engine.get_macro_data()

    # ========== A股报告 ==========
    a_share_md = "**🇨🇳 【A股风控雷达】**\n\n"

    # 0. 短线情绪
    sentiment_data = fa.get_sentiment_data()
    if sentiment_data:
        sent = sentiment_data['sentiment']
        score = sent.get('sentiment_score', 0)
        verdict = sent.get('verdict', '---')
        suggestion = sent.get('suggestion', '')

        a_share_md += "*🔥 短线市场情绪*\n"
        score_emoji = "🔴" if score >= 80 else ("🟢" if score >= 60 else ("🟡" if score >= 40 else "🔴"))
        a_share_md += f"- **综合情绪评分**: {score} {score_emoji} {verdict}\n"

        mkt_sent = sent.get('market_sentiment', {})
        mkt_level = mkt_sent.get('level', 0)
        mkt_verdict = mkt_sent.get('verdict', '')
        mkt_emoji = {1:"🔴", 2:"🟠", 3:"🟡", 4:"🟢", 5:"🔴"}.get(mkt_level, "⚪")
        a_share_md += f"- **大盘情绪**: L{mkt_level} {mkt_emoji} {mkt_verdict}\n"
        for sig in mkt_sent.get('signals', []):
            a_share_md += f"  · {sig}\n"

        sec_sent = sent.get('sector_sentiment', {})
        sec_level = sec_sent.get('level', 0)
        sec_verdict = sec_sent.get('verdict', '')
        sec_emoji = {1:"🔴", 2:"🟠", 3:"🟡", 4:"🟢", 5:"🔴"}.get(sec_level, "⚪")
        a_share_md += f"- **题材情绪**: L{sec_level} {sec_emoji} {sec_verdict}\n"
        for sig in sec_sent.get('signals', []):
            a_share_md += f"  · {sig}\n"

        if suggestion:
            a_share_md += f"- 💡 **操作建议**: {suggestion}\n"

        top5 = sentiment_data.get('top5', [])
        if top5:
            a_share_md += "  🏆 **Top5标的**: "
            top_strs = []
            for s in top5[:5]:
                lt = s.get('limit_times', 1)
                tag = f"{lt}连板" if lt > 1 else "首板"
                top_strs.append(f"{s.get('name','')}{tag}")
            a_share_md += " | ".join(top_strs) + "\n"

        a_share_md += "\n"

    # 1. 资金杠杆
    a_share_md += "*🏛️ 资金杠杆与情绪*\n"
    if margin_val and mkt_metrics:
        margin_ratio = (margin_val / mkt_metrics['float_mv']) * 100
        status_mb = "🔴 极度疯狂" if margin_val > 2.0 else ("🟡 情绪过热" if margin_val > 1.8 else "🟢 情绪温和")
        status_mr = "🔴 杠杆爆表" if margin_ratio > 4.0 else ("🟡 杠杆偏高" if margin_ratio > 3.0 else "🟢 结构健康")
        a_share_md += f"- **两融余额**: {margin_val:.2f}万亿 ({status_mb})\n"
        a_share_md += f"- **杠杆占比**: {margin_ratio:.2f}% ({status_mr})\n"
    else:
        a_share_md += "- **两融数据**: 获取失败\n"

    # 2. 经济景气度
    pmi = macro.get('pmi')
    pmi_month = macro.get('pmi_month', '')
    if len(pmi_month) > 4:
        pmi_month = pmi_month[4:]
    gdp_yoy = macro.get('gdp_yoy')
    a_share_md += "\n*🏭 经济景气度 (Growth)*\n"
    if pmi is not None:
        _, s_pmi = fa.analyze_pmi(pmi)
        a_share_md += f"- **制造业PMI({pmi_month})**: {pmi:.1f} ({s_pmi})\n"
    if gdp_yoy is not None:
        gdp_quarter = macro.get('gdp_quarter', '')
        a_share_md += f"- **GDP同比({gdp_quarter})**: {gdp_yoy:.1f}% \n"

    # 3. 估值锚
    total_mv = mkt_metrics['total_mv'] if mkt_metrics else None
    gdp = macro.get('annual_gdp', fa.MANUAL_GDP_ESTIMATE)
    a_share_md += "\n*🌏 整体估值锚 (Valuation)*\n"
    if total_mv:
        buffett = (total_mv / gdp) * 100
        if buffett > 120: s_bf = "🔴 07年泡沫"
        elif buffett > 100: s_bf = "🔴 15年泡沫"
        elif buffett > 80: s_bf = "🟡 估值偏高"
        else: s_bf = "🟢 估值安全"
        a_share_md += f"- **A股总市值**: {total_mv:.2f} 万亿\n"
        a_share_md += f"- **GDP总量**: {gdp:.2f} 万亿\n"
        a_share_md += f"- **巴菲特指标**: {buffett:.1f}% ({s_bf})\n"

    # 4. 通胀与货币
    cpi = macro.get('cpi')
    ppi = macro.get('ppi')
    sci = macro.get('scissors')
    m2 = macro.get('m2')
    sf_inc = macro.get('sf_inc')
    
    a_share_md += "\n*💸 通胀与货币 (Inflation & Money)*\n"
    if cpi is not None:
        _, s_cpi = fa.analyze_cpi(cpi)
        a_share_md += f"- **CPI同比**: {cpi:.1f}% ({s_cpi})\n"
    if ppi is not None:
        _, s_ppi = fa.analyze_ppi(ppi)
        a_share_md += f"- **PPI同比**: {ppi:.1f}% ({s_ppi})\n"
    if sci is not None:
        _, s_sci = fa.analyze_scissors(sci)
        a_share_md += f"- **M1-M2剪刀差**: {sci:.1f}% ({s_sci})\n"
    if m2 is not None:
        a_share_md += f"- **M2增速**: {m2:.1f}% \n"
    if sf_inc is not None:
        a_share_md += f"- **社融当月增量**: {sf_inc:.0f} 亿\n"

    # ========== 全球报告 ==========
    print(">>> 正在抓取 全球宏观 数据 (CNBC & FRED)...")
    cnbc_symbols = {
        'btc': "BTC.CB=", 'gold': "@GC.1", 'silver': "@SI.1",
        'copper': "@HG.1", 'oil': "@CL.1",
        'us10y': "US10Y", 'us2y': "US2Y", 'jp10y': "JP10Y",
        'dxy': ".DXY", 'usdcnh': "CNH=", 'vix': ".VIX"
    }
    fred_series = {
        'hy_spread': "BAMLH0A0HYM2"
    }
    
    # CNBC 替代 FRED 的 TIPS 数据（国内可访问）
    cnbc_symbols['tips_10y'] = "US10YTIP"
    
    all_data = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for key, sym in cnbc_symbols.items():
            futures[executor.submit(fetch_cnbc_fast, sym)] = ('cnbc', key)
        for key, sid in fred_series.items():
            futures[executor.submit(fetch_fred_fast, sid)] = ('fred', key)
        for future in as_completed(futures, timeout=30):
            try:
                result = future.result(timeout=10)
                src, key = futures[future]
                all_data[key] = result
            except:
                pass

    def get_val(key): return all_data.get(key, (None, None))[0]
    def get_chg(key): return all_data.get(key, (None, None))[1]

    btc, btc_chg = get_val('btc'), get_chg('btc')
    gold, gold_chg = get_val('gold'), get_chg('gold')
    silver, silver_chg = get_val('silver'), get_chg('silver')
    copper, copper_chg = get_val('copper'), get_chg('copper')
    oil, oil_chg = get_val('oil'), get_chg('oil')
    us10y, us10y_chg = get_val('us10y'), get_chg('us10y')
    us2y, us2y_chg = get_val('us2y'), get_chg('us2y')
    jp10y, jp10y_chg = get_val('jp10y'), get_chg('jp10y')
    dxy, dxy_chg = get_val('dxy'), get_chg('dxy')
    usdcnh, usdcnh_chg = get_val('usdcnh'), get_chg('usdcnh')
    vix, vix_chg = get_val('vix'), get_chg('vix')
    hy_spread = get_val('hy_spread')
    tips_10y = get_val('tips_10y')
    real_yield_10y = tips_10y
    breakeven_inflation = None
    if us10y and tips_10y:
        breakeven_inflation = us10y - tips_10y

    global_md = "\n---\n**🌍 【全球周期罗盘】**\n\n"
    
    # 1. 周期罗盘
    global_md += "*🧭 周期罗盘*\n"
    cg_ratio = (copper * 100) / gold if (copper and gold) else None
    curve_10y2y = (us10y - us2y) * 100 if (us10y and us2y) else None
    
    if gold and cg_ratio:
        _, kw_txt = fg.analyze_kwave(gold, cg_ratio)
        global_md += f"- **康波周期**: {kw_txt} (铜金比: {cg_ratio:.2f})\n"
    if curve_10y2y is not None and hy_spread is not None:
        _, kz_txt = fg.analyze_kuznets(curve_10y2y, hy_spread)
        global_md += f"- **库兹涅茨(地产信用)**: {kz_txt} (利差: {curve_10y2y:.0f}bp)\n"
    if gold and dxy:
        _, dc_txt = fg.analyze_debt_cycle(gold, dxy)
        global_md += f"- **长期债务周期**: {dc_txt}\n"
    if vix and gold:
        _, ft_txt = fg.analyze_4th_turning(vix, gold)
        global_md += f"- **第四次转折(地缘)**: {ft_txt}\n"

    # 2. 宏观比价 + 解读
    global_md += "\n*⚖️ 宏观比价*\n"
    gs_val = None
    go_val = None
    if gold and silver:
        gs_val = gold / silver
        s_gs = "🔴 通缩/避险" if gs_val > 85 else ("🟡 需关注" if gs_val > 70 else "🟢 复苏/通胀")
        global_md += f"- **金银比 (G/S)**: {gs_val:.1f} ({s_gs})\n"
        global_md += f"  > 金银比>85=恐惧(通缩)，<70=贪婪(复苏)\n"
    if gold and oil:
        go_val = gold / oil
        s_go = "🔴 极度衰退/战争" if go_val > 50 else ("🟡 避险主导" if go_val > 30 else "🟢 需求正常")
        global_md += f"- **金油比 (Au/Oil)**: {go_val:.1f} ({s_go})\n"
        global_md += f"  > 金油比>50=经济停摆，<30=需求正常\n"
    if cg_ratio:
        s_cg = "🟢 经济扩张" if cg_ratio > 0.20 else ("🟡 增长放缓" if cg_ratio > 0.15 else "🔴 衰退风险")
        global_md += f"- **铜金比 (Cu/Au)**: {cg_ratio:.2f} ({s_cg})\n"
        global_md += f"  > 铜金比上升=资金回流实业，下降=衰退预警\n"
    if gold and copper:
        gc = gold / copper
        s_gc = "🔴 避险爆表" if gc > 750 else ("🟡 避险升温" if gc > 650 else "🟢 情绪稳定")
        global_md += f"- **金铜比 (Au/Cu)**: {gc:.1f} ({s_gc})\n"
        global_md += f"  > 金铜比>750=避险远超实业，经济冰点\n"

    # 综合研判
    global_md += "\n*🔑 综合研判*\n"
    signals = []
    if gs_val and gs_val < 70:
        signals.append(("🟢", "金银比偏低→白银强，工业需求尚可"))
    elif gs_val and gs_val > 85:
        signals.append(("🔴", "金银比偏高→避险情绪浓厚，通缩压力"))
    if go_val and go_val > 50:
        signals.append(("🔴", "金油比过50→油价弱或金价强，经济运转不畅"))
    elif go_val and go_val < 30:
        signals.append(("🟢", "金油比正常→原油需求旺盛，经济活跃"))
    if cg_ratio and cg_ratio < 0.15:
        signals.append(("🔴", "铜金比偏低→铜弱金强，实业萎缩"))
    elif cg_ratio and cg_ratio > 0.20:
        signals.append(("🟢", "铜金比偏高→资金回流实业，经济扩张"))
    if vix and vix > 20:
        signals.append(("🟡", "VIX偏高→市场波动加剧，注意风险"))
    elif vix and vix < 15:
        signals.append(("🟢", "VIX低位→市场平稳，风险偏好较好"))
    
    if not signals:
        global_md += "暂无明显信号\n"
    else:
        red_count = sum(1 for s in signals if s[0] == "🔴")
        green_count = sum(1 for s in signals if s[0] == "🟢")
        for icon, text in signals:
            global_md += f"- {icon} {text}\n"
        if red_count >= 2:
            global_md += "\n⚠️ **多重衰退信号共振，建议防御为主，关注黄金板块和低估值品种**\n"
        elif green_count >= 2:
            global_md += "\n✅ **复苏信号占优，可关注顺周期品种和成长股**\n"
        else:
            global_md += "\n🔄 **信号分歧，建议均衡配置，既守又攻**\n"

    # 3. 流动性与债市
    global_md += "\n*💧 流动性与通胀*\n"
    if real_yield_10y is not None:
        s_ry = "🟢 宽松/金牛" if real_yield_10y < 1.0 else "🔴 紧缩/杀估值"
        global_md += f"- **10Y真实利率(TIPS)**: {real_yield_10y:.2f}% ({s_ry})\n"
    else:
        global_md += f"- **10Y真实利率(TIPS)**: 数据缺失\n"
    if breakeven_inflation is not None:
        s_be = "🟢 通胀温和" if breakeven_inflation < 2.0 else ("🟡 通胀偏高" if breakeven_inflation < 3.0 else "🔴 通胀过热")
        global_md += f"- **盈亏平衡通胀预期**: {breakeven_inflation:.2f}% ({s_be})\n"
        global_md += f"  > 通胀预期=10Y名义利率-TIPS真实利率，反映市场对未来10年通胀的定价\n"
    else:
        global_md += f"- **盈亏平衡通胀预期**: 需10Y+TIPS数据\n"
    if us10y and jp10y:
        global_md += f"- **美日利差**: {(us10y - jp10y) * 100:.0f} bp\n"

    # 4. 风险与核心资产
    global_md += "\n*🅰️ 风险与核心资产*\n"
    s_dxy = "🔴 极度紧缩" if dxy and dxy > 106 else ("🟡 流动性紧" if dxy and dxy > 103 else "🟢 宽裕")
    global_md += f"- **美元指数(DXY)**: {dxy} ({s_dxy})\n"
    s_vix = "🔴 极度恐慌" if vix and vix > 30 else ("🟡 波动加剧" if vix and vix > 20 else "🟢 市场平稳")
    global_md += f"- **VIX恐慌指数**: {vix} ({s_vix})\n"
    
    btc_str = f"${btc:,.2f}" if btc else "N/A"
    gold_str = f"${gold:,.2f}" if gold else "N/A"
    oil_str = f"${oil:,.2f}" if oil else "N/A"
    global_md += f"- 🪙 **BTC**: {btc_str} | 🌕 **黄金**: {gold_str} | 🛢️ **原油**: {oil_str}\n"

    return a_share_md + global_md


if __name__ == '__main__':
    print("🚀 启动自动化数据汇总引擎...")
    md_text = generate_report()
    print("\n📦 成功组装汇报内容，准备推送到飞书终端...")
    push_to_feishu(md_text)

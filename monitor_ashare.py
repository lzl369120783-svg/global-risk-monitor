import akshare as ak
import pandas as pd
import datetime
import time
import os
import sys
import json
import glob
import unicodedata

# 修复 Windows 终端 GBK 编码问题
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass

# ==============================================================================
# 0. 配置区域
# ==============================================================================
# 从配置文件读取敏感信息（config.py 不提交 Git）
try:
    from config import ASTOCK_OUTPUT_DIR
except ImportError:
    ASTOCK_OUTPUT_DIR = r"C:\Users\Administrator\WorkBuddy\20260410111908\astock_analyzer\output"

# 2025年确切GDP总量 (万亿)
MANUAL_GDP_ESTIMATE = 140.19

# 历史风险参考值
RISK_MARGIN_PEAK_2015 = 2.27
RISK_BUFFETT_PEAK_2007 = 125
RISK_BUFFETT_PEAK_2015 = 110

# ==============================================================================
# 1. 终端颜色与工具
# ==============================================================================
os.system('')
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GREY = '\033[90m'
    BLUE = '\033[94m'

def get_status_color(val, high, low, reverse=False):
    if val is None: return Colors.GREY
    if not reverse:
        return Colors.RED if val >= high else (Colors.YELLOW if val >= low else Colors.GREEN)
    else:
        return Colors.RED if val <= low else (Colors.YELLOW if val <= high else Colors.GREEN)

# ==============================================================================
# 2. AKShare 数据引擎
# ==============================================================================
class AKShareEngine:
    def __init__(self):
        pass

    def get_latest_margin(self):
        """获取沪深两市两融余额（万亿）"""
        print(f"{Colors.GREY}   正在获取两融数据 (沪深合并)...{Colors.RESET}")
        total_margin = None
        date_str = None
        try:
            # 沪市两融
            end_date = datetime.datetime.now().strftime('%Y%m%d')
            start_date = (datetime.datetime.now() - datetime.timedelta(days=15)).strftime('%Y%m%d')
            df_sh = ak.stock_margin_sse(start_date=start_date, end_date=end_date)
            sh_margin = 0
            sh_date = None
            if df_sh is not None and len(df_sh) > 0:
                last = df_sh.iloc[-1]
                sh_margin = float(last['融资融券余额'])
                sh_date = str(last['信用交易日期'])

            # 深市两融 - 用 stock_margin_detail_szse 获取汇总
            # 深市汇总接口不太稳定，备选方案：只取沪市再估算
            try:
                df_sz = ak.stock_margin_szse(date=end_date)
                if df_sz is not None and len(df_sz) > 0:
                    sz_margin = df_sz['融资融券余额'].sum()
                else:
                    sz_margin = sh_margin * 0.45  # 深市约占沪市45%
            except:
                sz_margin = sh_margin * 0.45

            total_margin = (sh_margin + sz_margin) / 1e12  # 万亿
            date_str = sh_date
        except Exception as e:
            print(f"{Colors.GREY}   两融获取异常: {str(e)[:50]}{Colors.RESET}")

        return total_margin, date_str

    def get_market_metrics(self):
        """获取全市场市值（万亿）"""
        print(f"{Colors.GREY}   正在计算全市场市值 (沪深汇总)...{Colors.RESET}")
        try:
            total_mv = 0
            float_mv = 0

            # 沪市
            df_sh = ak.stock_sse_summary()
            sh_row = df_sh[df_sh['项目'] == '总市值']
            if len(sh_row) > 0:
                total_mv += float(sh_row.iloc[0]['股票'])
            sh_float = df_sh[df_sh['项目'] == '流通市值']
            if len(sh_float) > 0:
                float_mv += float(sh_float.iloc[0]['股票'])

            # 深市
            df_sz = ak.stock_szse_summary()
            sz_stock = df_sz[df_sz['证券类别'] == '股票']
            if len(sz_stock) > 0:
                total_mv += float(sz_stock.iloc[0]['总市值'])
                float_mv += float(sz_stock.iloc[0]['流通市值'])

            # 转换为万亿（原始单位：亿元）
            return {
                'total_mv': total_mv / 1e4,
                'float_mv': float_mv / 1e4
            }
        except Exception as e:
            print(f"{Colors.GREY}   市值获取异常: {str(e)[:50]}{Colors.RESET}")
            return None

    def get_macro_data(self):
        """获取宏观经济数据"""
        print(f"{Colors.GREY}   正在获取宏观经济数据 (PMI/GDP/CPI/社融)...{Colors.RESET}")
        data = {}

        # 1. GDP
        try:
            df = ak.macro_china_gdp()
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]
                data['gdp_yoy'] = float(latest['国内生产总值-同比增长'])
                data['gdp_quarter'] = latest['季度']
                acc_gdp = float(latest['国内生产总值-绝对值']) / 1e4
                if "四" in str(latest['季度']) or "4" in str(latest['季度']):
                    data['annual_gdp'] = acc_gdp
                else:
                    data['annual_gdp'] = MANUAL_GDP_ESTIMATE
        except:
            data['annual_gdp'] = MANUAL_GDP_ESTIMATE

        # 2. PMI
        try:
            df = ak.macro_china_pmi()
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]
                data['pmi'] = float(latest['制造业-指数'])
                data['pmi_month'] = latest['月份']
        except: pass

        # 3. M1/M2
        try:
            df = ak.macro_china_money_supply()
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]
                data['m1'] = float(latest['货币(M1)-同比增长'])
                data['m2'] = float(latest['货币和准货币(M2)-同比增长'])
                data['scissors'] = data['m1'] - data['m2']
        except: pass

        # 4. CPI/PPI
        try:
            df_c = ak.macro_china_cpi()
            if df_c is not None and len(df_c) > 0:
                latest = df_c.iloc[-1]
                data['cpi'] = float(latest['全国-同比增长'])
                data['cpi_month'] = latest['月份']
        except: pass

        try:
            df_p = ak.macro_china_ppi()
            if df_p is not None and len(df_p) > 0:
                latest = df_p.iloc[-1]
                data['ppi'] = float(latest['当月同比增长'])
        except: pass

        # 5. 社融
        try:
            df = ak.macro_china_shrzgm()
            if df is not None and len(df) > 0:
                latest = df.iloc[-1]
                data['sf_inc'] = float(latest['社会融资规模增量'])
        except: pass

        return data

# ==============================================================================
# 2.5 短线情绪引擎 (读取 astock_analyzer 数据)
# ==============================================================================
def get_sentiment_data():
    """从 astock_analyzer 输出中读取最新情绪数据"""
    print(f"{Colors.GREY}   正在读取短线情绪数据 (astock_analyzer)...{Colors.RESET}")
    try:
        # 找最新的 review 文件
        today = datetime.datetime.now().strftime('%Y%m%d')
        review_file = os.path.join(ASTOCK_OUTPUT_DIR, f"review_{today}.json")
        
        if not os.path.exists(review_file):
            # 找最近的 review 文件
            review_files = sorted(glob.glob(os.path.join(ASTOCK_OUTPUT_DIR, "review_*.json")), reverse=True)
            if review_files:
                review_file = review_files[0]
            else:
                return None
        
        with open(review_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        sentiment = data.get('sentiment', {})
        top5 = data.get('top5', [])
        
        return {
            'sentiment': sentiment,
            'top5': top5,
            'date': data.get('trade_date', '')
        }
    except Exception as e:
        print(f"{Colors.GREY}   情绪数据读取异常: {str(e)[:50]}{Colors.RESET}")
        return None

def get_sentiment_emoji(level):
    """根据情绪等级返回 emoji 和颜色"""
    mapping = {
        1: (Colors.RED, "🔴 L1 冰点"),
        2: (Colors.YELLOW, "🟠 L2 低迷"),
        3: (Colors.YELLOW, "🟡 L3 中性"),
        4: (Colors.GREEN, "🟢 L4 偏强"),
        5: (Colors.RED, "🔴 L5 亢奋"),
    }
    return mapping.get(level, (Colors.GREY, "⚪ 无数据"))

# ==============================================================================
# 3. 智能研判逻辑 (Brain)
# ==============================================================================
def analyze_pmi(val):
    if val is None: return Colors.GREY, "无数据"
    if val > 50.0: return Colors.GREEN, "🟢 行业扩张 (利好)"
    elif val == 50.0: return Colors.YELLOW, "🟡 景气持平"
    else: return Colors.RED, "🔴 行业收缩 (利空)"

def analyze_scissors(val):
    if val is None: return Colors.GREY, "无数据"
    if val > 0: return Colors.GREEN, "🟢 资金活化 (牛市动力)"
    elif val > -5: return Colors.YELLOW, "🟡 存款定期化 (温和利空)"
    else: return Colors.RED, "🔴 流动性陷阱 (极差)"

def analyze_cpi(val):
    if val is None: return Colors.GREY, "无数据"
    if val < 0: return Colors.RED, "🔴 通缩 (需求不足)"
    elif val <= 3.0: return Colors.GREEN, "🟢 温和通胀 (健康)"
    else: return Colors.RED, "🔴 高通胀 (政策收紧)"

def analyze_ppi(val):
    if val is None: return Colors.GREY, "无数据"
    if val > 0: return Colors.GREEN, "🟢 工业回暖 (利润修复)"
    else: return Colors.YELLOW, "🟡 工业通缩 (利润承压)"

# ==============================================================================
# 4. 渲染工具
# ==============================================================================
def get_display_width(s):
    w = 0
    for char in s:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            w += 2
        else:
            w += 1
    return w

def pad_str(s, width, align='left'):
    current_width = get_display_width(s)
    padding_len = max(0, width - current_width)
    padding = ' ' * padding_len
    if align == 'left':
        return s + padding
    elif align == 'right':
        return padding + s
    else:
        left_pad = padding_len // 2
        right_pad = padding_len - left_pad
        return ' ' * left_pad + s + ' ' * right_pad

def print_row(label, val_str, status_color, status_text):
    label_padded = pad_str(label, 22, 'left')
    val_padded = pad_str(val_str, 14, 'right')
    print(f" {label_padded} │ {Colors.WHITE}{val_padded}{Colors.RESET} │ {status_color}{status_text}{Colors.RESET}")

def print_sub_row(label, val_str, status_text):
    label_padded = pad_str(label, 17, 'left')
    val_padded = pad_str(val_str, 14, 'right')
    print(f"    ↳ {label_padded} │ {Colors.GREY}{val_padded}{Colors.RESET} │ {Colors.GREY}{status_text}{Colors.RESET}")

def print_header(title):
    title_padded = pad_str(title, 54, 'left')
    print(f"{Colors.GREY} ┌──────────────────────┬────────────────┬──────────────────────┐{Colors.RESET}")
    print(f"{Colors.GREY} │ {Colors.BOLD}{title_padded}{Colors.GREY} │{Colors.RESET}")
    print(f"{Colors.GREY} ├──────────────────────┼────────────────┼──────────────────────┤{Colors.RESET}")

def print_footer():
    print(f"{Colors.GREY} └──────────────────────┴────────────────┴──────────────────────┘{Colors.RESET}")

# ==============================================================================
# 主程序
# ==============================================================================
def main():
    os.system('cls' if os.name == 'nt' else 'clear')

    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{Colors.CYAN}{'='*66}")
    print(f" 📈 A股宏观风控终端 | {now_str}")
    print(f"{'='*66}{Colors.RESET}")

    engine = AKShareEngine()

    # 获取数据
    margin_val, _ = engine.get_latest_margin()
    mkt_metrics = engine.get_market_metrics()
    macro = engine.get_macro_data()
    sentiment_data = get_sentiment_data()

    # --- 开始渲染 ---
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"{Colors.CYAN}{'='*66}")
    print(f" 📈 A股宏观风控终端 (V2.5-AKShare) | {now_str}")
    print(f"{'='*66}{Colors.RESET}")

    h1 = pad_str("核心指标", 22)
    h2 = pad_str("数值", 14, 'right')
    print(f" {Colors.BOLD}{h1} │ {h2} │ 智能研判/历史对标{Colors.RESET}")

    # =========================================
    # 0. 短线情绪 (Sentiment)
    # =========================================
    print_header("🔥 短线市场情绪 (Sentiment)")

    if sentiment_data:
        sent = sentiment_data['sentiment']
        score = sent.get('sentiment_score', 0)
        verdict = sent.get('verdict', '---')
        suggestion = sent.get('suggestion', '')

        # 综合情绪评分
        if score >= 80: score_color = Colors.RED
        elif score >= 60: score_color = Colors.GREEN
        elif score >= 40: score_color = Colors.YELLOW
        else: score_color = Colors.RED
        print_row("🎯 综合情绪评分", f"{score}", score_color, verdict)

        # 大盘情绪
        mkt_sent = sent.get('market_sentiment', {})
        mkt_level = mkt_sent.get('level', 0)
        mkt_verdict = mkt_sent.get('verdict', '---')
        mkt_color, mkt_label = get_sentiment_emoji(mkt_level)
        print_row("📊 大盘情绪", f"L{mkt_level}", mkt_color, mkt_verdict)
        for sig in mkt_sent.get('signals', []):
            print_sub_row("· " + sig, "", "")

        # 题材情绪
        sec_sent = sent.get('sector_sentiment', {})
        sec_level = sec_sent.get('level', 0)
        sec_verdict = sec_sent.get('verdict', '---')
        sec_color, sec_label = get_sentiment_emoji(sec_level)
        print_row("🎯 题材情绪", f"L{sec_level}", sec_color, sec_verdict)
        for sig in sec_sent.get('signals', []):
            print_sub_row("· " + sig, "", "")

        # 操作建议
        if suggestion:
            sug_color = Colors.GREEN if '参与' in suggestion or '积极' in suggestion else (
                Colors.YELLOW if '谨慎' in suggestion or '轻仓' in suggestion else Colors.RED)
            print_row("💡 操作建议", "", sug_color, suggestion)

        # Top5 标的
        top5 = sentiment_data.get('top5', [])
        if top5:
            print_footer()
            print(f"{Colors.GREY}   🏆 今日Top5标的:{Colors.RESET}")
            for i, stock in enumerate(top5[:5], 1):
                name = stock.get('name', '')
                score_val = stock.get('total_score', 0)
                desc = stock.get('lu_desc', '')[:25]
                lt = stock.get('limit_times', 1)
                tag = f"{lt}连板" if lt > 1 else "首板"
                print(f"{Colors.GREY}     {i}. {Colors.WHITE}{name}{Colors.GREY} | {tag} | {score_val:.0f}分 | {desc}{Colors.RESET}")
    else:
        print_row("情绪数据", "---", Colors.GREY, "非交易时段/无数据")

    print_footer()

    # =========================================
    # 1. 资金杠杆 (Leverage)
    # =========================================
    print_header("🏛️  资金杠杆与情绪 (Leverage)")

    if margin_val and mkt_metrics:
        c_mb = get_status_color(margin_val, 2.0, 1.8)
        s_mb = "🔴 极度疯狂" if margin_val > 2.0 else ("🟡 情绪过热" if margin_val > 1.8 else "🟢 情绪温和")
        print_row("💰 两融余额", f"{margin_val:.2f} 万亿", c_mb, s_mb)

        margin_ratio = (margin_val / mkt_metrics['float_mv']) * 100
        c_mr = get_status_color(margin_ratio, 4.0, 3.0)
        s_mr = "🔴 杠杆爆表" if margin_ratio > 4.0 else ("🟡 杠杆偏高" if margin_ratio > 3.0 else "🟢 结构健康")
        print_row("📊 两融/流通市值比", f"{margin_ratio:.2f} %", c_mr, s_mr)

        print_footer()
        print(f"{Colors.GREY}   📚 2015牛市顶参考: 两融余额 2.27万亿 / 占比 4.5%{Colors.RESET}")
    else:
        print_row("数据获取失败", "---", Colors.RED, "检查接口")
        print_footer()

    # =========================================
    # 2. 经济景气度 (Growth)
    # =========================================
    print_header("🏭 经济景气度 (Growth)")

    pmi = macro.get('pmi')
    c_pmi, s_pmi = analyze_pmi(pmi)
    pmi_month = macro.get('pmi_month', '')
    # 处理月份格式
    if len(pmi_month) > 4:
        pmi_month = pmi_month[4:]
    print_row(f"🏭 制造业PMI ({pmi_month})", f"{pmi:.1f}" if pmi else "---", c_pmi, s_pmi)

    if 'gdp_yoy' in macro:
        val = macro['gdp_yoy']
        c_gdp = get_status_color(val, 6.0, 5.0, reverse=True)
        s_gdp = f"{macro.get('gdp_quarter','')} 增速"
        print_row("🌏 GDP同比增速", f"{val:.1f} %", c_gdp, s_gdp)
    else:
        print_row("🌏 GDP同比增速", "---", Colors.GREY, "数据待更新")

    print_footer()

    # =========================================
    # 3. 估值锚 (Valuation)
    # =========================================
    print_header("🌏 整体估值锚 (Valuation)")

    if mkt_metrics:
        total_mv = mkt_metrics['total_mv']
        gdp = macro.get('annual_gdp', MANUAL_GDP_ESTIMATE)

        print_row("📉 A股总市值", f"{total_mv:.2f} 万亿", Colors.WHITE, "---")
        print_row("🌏 2025年GDP总量", f"{gdp:.2f} 万亿", Colors.WHITE, "---")

        buffett = (total_mv / gdp) * 100
        c_bf = get_status_color(buffett, 100, 80)

        if buffett > 120: s_bf = "🔴 07年级泡沫"
        elif buffett > 100: s_bf = "🔴 15年级泡沫"
        elif buffett > 80: s_bf = "🟡 估值偏高"
        else: s_bf = "🟢 估值安全"

        print_row("📏 市值/GDP (巴菲特)", f"{buffett:.1f} %", c_bf, s_bf)

        print_footer()
        print(f"{Colors.GREY}   📚 历史大顶比值参考:{Colors.RESET}")
        print(f"{Colors.GREY}      • 2007年疯牛顶: ~{RISK_BUFFETT_PEAK_2007}%{Colors.RESET}")
        print(f"{Colors.GREY}      • 2015年疯牛顶: ~{RISK_BUFFETT_PEAK_2015}%{Colors.RESET}")
        print(f"{Colors.GREY}      • 底部安全区间: 40% - 60%{Colors.RESET}")
    else:
        print_footer()

    # =========================================
    # 4. 通胀与货币 (Inflation & Liquidity)
    # =========================================
    print_header("💸 通胀与货币 (Inflation & Money)")

    cpi = macro.get('cpi')
    c_cpi, s_cpi = analyze_cpi(cpi)
    cpi_m_str = macro.get('cpi_month','')
    if len(cpi_m_str) > 4:
        cpi_m_str = cpi_m_str[4:]
    print_row(f"🛒 CPI同比 ({cpi_m_str})", f"{cpi:.1f} %" if cpi else "---", c_cpi, s_cpi)

    ppi = macro.get('ppi')
    c_ppi, s_ppi = analyze_ppi(ppi)
    print_row("🏭 PPI同比", f"{ppi:.1f} %" if ppi else "---", c_ppi, s_ppi)

    sci = macro.get('scissors')
    m2 = macro.get('m2')
    c_sci, s_sci = analyze_scissors(sci)
    print_row("✂️  M1-M2 剪刀差", f"{sci:.1f} %" if sci else "---", c_sci, s_sci)
    if m2:
        print_sub_row("M2增速", f"{m2:.1f} %", "印钞速度")

    if 'sf_inc' in macro:
        print_row("💧 社融当月增量", f"{macro['sf_inc']:.0f} 亿", Colors.WHITE, "信用扩张")

    print_footer()
    print(f"\n{Colors.CYAN}{'='*66}{Colors.RESET}")

if __name__ == "__main__":
    main()
    input("按回车键退出...")

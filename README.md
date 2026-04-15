# 🌍 全球风险监控信息 (MacroGodEye)

> A股+全球宏观风控监控终端，支持终端展示和飞书推送

## 功能模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 🔥 A股风控雷达 | `monitor_ashare.py` | 两融/PMI/巴菲特指标/CPI+短线情绪 |
| 🌍 全球周期罗盘 | `monitor_global.py` | 黄金/原油/美债/VIX/宏观比价 |
| 📡 飞书推送引擎 | `monitor_feishu.py` | 综合报告一键推飞书 |

## 快速开始

### 1. 安装依赖

```bash
python -m venv venv
venv\Scripts\activate
pip install akshare pandas requests beautifulsoup4
```

### 2. 配置

复制示例配置并填入你的值：

```bash
copy config.example.py config.py
```

编辑 `config.py`，填入：
- `FEISHU_WEBHOOK` — 飞书机器人 Webhook 地址
- `FEISHU_SECRET` — 飞书机器人签名密钥
- `ASTOCK_OUTPUT_DIR` — astock_analyzer 输出路径（短线情绪数据）

### 3. 运行

```bash
# A股风控雷达
run_ashare.bat

# 全球周期罗盘
run_global.bat

# 飞书推送
run_feishu.bat
```

## 数据源

| 数据 | 来源 | 备注 |
|------|------|------|
| A股两融/市值/宏观 | AKShare | 免费无需注册 |
| 全球商品/债市/外汇 | CNBC | 实时行情 |
| 10Y TIPS真实利率 | CNBC | 国内可访问 |
| 短线情绪评分 | astock_analyzer | 本地JSON数据 |

## 注意事项

- `config.py` 包含敏感信息，已被 `.gitignore` 排除，不会提交到 Git
- FRED 数据源（fred.stlouisfed.org）在国内无法访问，部分指标可能显示缺失
- 高收益债利差仍走 FRED，国内超时则留空

## 致谢

基于 [MacroGodEye](https://github.com/cslht/MacroGodEye) 改造，主要改动：
- Tushare → AKShare（免费数据源）
- 新增短线情绪模块（大盘/题材情绪评分+操作建议）
- 新增宏观比价解读+综合研判
- 飞书推送加签名校验
- FRED → CNBC 替代国内不可访问数据源
- Windows GBK 编码修复
- 网络请求并发优化

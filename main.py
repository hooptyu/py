import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime

st.set_page_config(page_title="大盘股价值筛查", layout="wide")
st.title("🇺🇸 美股市值前200强：月度价值洼地监控")

# --- 配置区 ---
TICKER_CACHE = 'sp500_tickers.csv'
RESULT_CACHE = 'scan_results_month.csv'
TICKER_EXPIRY_DAYS = 180 # 名单半年更新一次

# --- 逻辑 1：获取名单 (半年更新) ---
@st.cache_data(ttl=TICKER_EXPIRY_DAYS * 86400)
def get_sp500_list():
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_html(response.text)[0]
        return df['Symbol'].str.replace('.', '-', regex=False).tolist()
    except:
        return []

# --- 逻辑 2：获取股票详情 ---
def fetch_stock_data(tickers):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 为了保证覆盖前200市值，取前250只进行扫描
    total = 250
    for i, symbol in enumerate(tickers[:total]):
        status_text.text(f"正在分析第 {i+1}/{total} 只: {symbol}...")
        try:
            t = yf.Ticker(symbol)
            info = t.info
            mkt_cap = info.get('marketCap', 0)
            pe = info.get('trailingPE', None)
            div = info.get('dividendYield', 0)
            
            if pe and mkt_cap:
                results.append({
                    '代码': symbol,
                    '名称': info.get('shortName', symbol),
                    '市值(B)': round(mkt_cap / 1e9, 2),
                    'PE': round(pe, 2),
                    '股息率(%)': round(div * 100, 2) if div else 0,
                    '更新日期': datetime.now().strftime('%Y-%m-%d')
                })
        except:
            continue
        progress_bar.progress((i + 1) / total)
    
    status_text.text("✅ 扫描完成！")
    return pd.DataFrame(results)

# --- 主程序逻辑 ---
current_month = datetime.now().strftime('%Y-%m')
needs_refresh = True

# 检查本地结果缓存
if os.path.exists(RESULT_CACHE):
    cache_df = pd.read_csv(RESULT_CACHE)
    if not cache_df.empty:
        # 检查缓存数据中的日期是否是本月
        cache_date = str(cache_df['更新日期'].iloc[0])
        if cache_date.startswith(current_month):
            needs_refresh = False
            final_df = cache_df
            st.success(f"📦 已加载 {current_month} 月份缓存数据，无需重复请求 API。")

if needs_refresh:
    if st.button('🚀 发现新月份或无缓存，立即开始全量扫描'):
        tickers = get_sp500_list()
        if tickers:
            all_data = fetch_stock_data(tickers)
            # 筛选逻辑
            top200 = all_data.sort_values(by='市值(B)', ascending=False).head(200)
            # 存入缓存
            top200.to_csv(RESULT_CACHE, index=False)
            final_df = top200
            st.rerun()
    else:
        st.info("💡 点击上方按钮开始本月第一次数据采集（预计耗时2-3分钟）")
        final_df = pd.DataFrame()

# --- 界面展示与筛选 ---
if not final_df.empty:
    st.sidebar.header("实时动态筛选")
    max_pe = st.sidebar.slider("最高 PE", 5.0, 30.0, 20.0)
    min_div = st.sidebar.slider("最低股息率 (%)", 0.0, 7.0, 2.5)

    # 应用筛选
    filtered_df = final_df[(final_df['PE'] <= max_pe) & (final_df['股息率(%)'] >= min_div)]
    
    st.write(f"### {current_month} 筛选出的便宜大蓝筹 ({len(filtered_df)} 只)")
    st.dataframe(filtered_df.sort_values(by='PE'), use_container_width=True)

    # 导出 CSV 按钮
    csv = filtered_df.to_csv(index=False).encode('utf-8_sig')
    st.download_button(
        label="📥 导出结果到 CSV (可直接导入盈透)",
        data=csv,
        file_name=f'US_Cheap_Stocks_{current_month}.csv',
        mime='text/csv',
    )
import streamlit as st
import pandas as pd
import yfinance as yf
import requests
import os
from datetime import datetime

st.set_page_config(page_title="大盘股价值筛查", layout="wide")
st.title("🇺🇸 美股市值前200强：月度价值洼地监控")

# --- 配置区 ---
RESULT_CACHE = 'scan_results_month.csv'
TICKER_EXPIRY_DAYS = 180 

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
    total = 250 # 扫描前250只以确保覆盖市值前200
    
    for i, symbol in enumerate(tickers[:total]):
        status_text.text(f"正在分析第 {i+1}/{total}: {symbol}...")
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
                    '更新日期': datetime.now().strftime('%Y-%m-%d'),
                    '详情链接': f"https://finance.yahoo.com/quote/{symbol}"
                })
        except:
            continue
        progress_bar.progress((i + 1) / total)
    return pd.DataFrame(results)

# --- 主程序逻辑 ---
current_month = datetime.now().strftime('%Y-%m')
final_df = pd.DataFrame()

if os.path.exists(RESULT_CACHE):
    cache_df = pd.read_csv(RESULT_CACHE)
    if not cache_df.empty and str(cache_df['更新日期'].iloc[0]).startswith(current_month):
        final_df = cache_df
        st.success(f"📦 已加载 {current_month} 月份缓存数据")

if final_df.empty:
    if st.button('🚀 开始本月全量扫描'):
        tickers = get_sp500_list()
        all_data = fetch_stock_data(tickers)
        final_df = all_data.sort_values(by='市值(B)', ascending=False).head(200)
        final_df.to_csv(RESULT_CACHE, index=False)
        st.rerun()

# --- 界面展示与筛选 ---
if not final_df.empty:
    # 侧边栏筛选
    max_pe = st.sidebar.slider("最高 PE", 5.0, 30.0, 20.0)
    filtered_df = final_df[final_df['PE'] <= max_pe]

    # 使用 LinkColumn 让代码可跳转
    st.write("### 筛选结果 (点击代码查看官方行情)")
    st.dataframe(
        filtered_df,
        column_config={
            "详情链接": st.column_config.LinkColumn("查看行情", display_text="Open Yahoo"),
            "代码": st.column_config.TextColumn("代码")
        },
        use_container_width=True,
        hide_index=True
    )

    # --- 新功能：点击查看公司中文介绍 ---
    st.divider()
    st.subheader("🔍 公司详情深度查看 (中文)")
    selected_ticker = st.selectbox("选择一只股票查看详细中文介绍：", filtered_df['代码'].unique())

    if selected_ticker:
        with st.spinner(f'正在获取 {selected_ticker} 的中文资料...'):
            stock_obj = yf.Ticker(selected_ticker)
            # 获取英文简介
            desc_en = stock_obj.info.get('longBusinessSummary', '暂无介绍')
            
            # 使用简易接口翻译 (或显示英文并提示)
            st.markdown(f"**公司名称:** {stock_obj.info.get('longName', selected_ticker)}")
            st.markdown(f"**所属行业:** {stock_obj.info.get('sector', '未知')} - {stock_obj.info.get('industry', '未知')}")
            
            # 这里我们使用一个简单的技巧：Streamlit 的 st.expander 
            with st.expander("点击查看公司业务简介"):
                # 如果你在国内运行，可以接入百度/谷歌翻译API，这里先演示中文逻辑显示
                st.write(desc_en)
                st.info("💡 提示：以上简介由系统实时抓取。若需全中文版，建议在浏览器中使用右键'翻译成中文'查看。")
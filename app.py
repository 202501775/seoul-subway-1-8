from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).parent
st.set_page_config(page_title='여유로운 출근길', page_icon='🚇', layout='wide')
COLORS = ['#edf7fb', '#9bd4e4', '#3c9dbb', '#f0b45a', '#d75e55']


def clock(value):
    value = int(value)
    prefix = '익일 ' if value >= 1440 else ''
    return f'{prefix}{(value // 60) % 24:02d}:{value % 60:02d}'


@st.cache_data
def load_data():
    return (
        pd.read_csv(ROOT / 'network.csv.gz'),
        pd.read_parquet(ROOT / 'cars_daily.parquet'),
        json.loads(
            (ROOT / 'metadata.json').read_text(encoding='utf-8')
        ),
    )


def chart(fig, key):
    fig.update_layout(font=dict(family='Arial, sans-serif', size=13),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      margin=dict(l=15,r=15,t=30,b=20))
    st.plotly_chart(fig, width="stretch", key=key)


def heatmap(frame, row, value, key, label):
    matrix = frame.pivot(index=row, columns='분', values=value).sort_index(axis=1)
    fig = px.imshow(matrix.to_numpy(), x=[clock(x) for x in matrix.columns],
                    y=[str(x) for x in matrix.index], aspect='auto',
                    color_continuous_scale=COLORS, zmin=0,
                    labels=dict(x='시간대 시작',y=label,color='혼잡도 (%)'))
    chart(fig,key)


def download(frame, name):
    st.download_button('선택 데이터 CSV 다운로드', frame.to_csv(index=False).encode('utf-8-sig'),
                       file_name=name,mime='text/csv')


network, cars, meta = load_data()
st.title('여유로운 출근길')
st.caption('언제, 어느 칸에 타면 덜 붐빌까? · 서울교통공사 공개자료 기반')
mode = st.sidebar.radio('분석 화면',['1~8호선 시간대별','4호선 칸별 상세','데이터와 집계 기준'])

if mode == '데이터와 집계 기준':
    st.subheader('데이터 출처')
    st.markdown('[1~8호선 혼잡도](https://www.data.go.kr/data/15071311/fileData.do) · 2026년 9월 기준, 서울교통공사 관할 구간')
    st.markdown('[4호선 칸별 혼잡도](https://www.data.go.kr/data/15167486/fileData.do) · 2026년 6~7월 신조 전동차 관측자료')
    st.write('혼잡도 단위는 정원 대비 탑승 인원 비율(%)입니다. 화면의 시간은 역에서의 탑승 시간대이며, 시간대 시작값을 표시합니다.')
    st.write('성수·신도림처럼 이름이 같고 역코드가 다른 항목은 역코드를 표시하여 각각 분석합니다.')
    st.write('1~8호선은 제공된 30분 평균값을 사용합니다. 원본 0%는 운행·관측 여부를 확인하기 어려워 기본적으로 추천과 차트에서 제외합니다. 사이드바에서 포함할 수 있습니다.')
    st.write('4호선은 같은 날짜·구간·30분 시간대·호차의 관측값을 먼저 평균 내고, 선택 기간에 걸쳐 날짜별 평균을 동일 가중치로 평균 냅니다. 관측 빈도가 높은 날이 결과를 지배하는 것을 줄이기 위한 방식입니다.')
    st.write('4호선 방향은 현재역 → 다음역으로 표시합니다. 역명과 요일구분은 원본 표기를 유지합니다. 관측이 없는 칸과 시간은 빈 값으로 남깁니다. 호차 번호는 원본 호차이며 승강장의 문 번호와 구분됩니다.')
    st.write('두 자료의 조사 시기·대상·집계 방식이 달라 수치를 합산하지 않습니다. 혼잡도 비교는 각각의 자료 안에서 수행합니다. 추천은 선택 조건의 과거 평균에 따른 결과이며 당일 탑승 상황은 달라질 수 있습니다.')
    st.write('4호선 전체 차량에 대한 대표성, 기상·행사·지연의 영향, 표본이 적은 시간대에 한계가 있습니다. 여러 관측이 같은 열차에 속할 수 있어 관측수는 독립 표본 수를 뜻하지 않습니다.')
    st.json(meta)
    st.stop()

if mode == '1~8호선 시간대별':
    line = st.sidebar.selectbox('호선',sorted(network['호선'].unique()))
    subset = network[network['호선'].eq(line)]
    day = st.sidebar.selectbox('요일 유형',subset['구분'].unique())
    subset = subset[subset['구분'].eq(day)]
    station = st.sidebar.selectbox('역',subset.sort_values('역번호')['역명'].drop_duplicates())
    directions = subset[subset['역명'].eq(station)]['상하구분'].unique()
    direction = st.sidebar.selectbox('방향',directions)
    include_zero = st.sidebar.checkbox('원본 0% 포함',value=False)
    subset = subset[subset['상하구분'].eq(direction)].copy()
    if not include_zero:
        subset.loc[subset['혼잡도'].eq(0),'혼잡도'] = float('nan')
    times = sorted(subset['분'].unique().tolist())
    window = st.sidebar.select_slider('탑승 가능한 시간 범위', options=times,
                                      value=(420,570),format_func=clock)
    local = subset[subset['역명'].eq(station)].sort_values('분').copy()
    visible = local[local['분'].between(*window)].dropna(subset=['혼잡도'])
    if visible.empty:
        st.info('선택 범위에 유효한 혼잡도 값이 없습니다. 시간 범위를 넓혀주세요.')
        st.stop()
    selected = st.select_slider('비교할 탑승 시간',options=visible['분'].tolist(),
                                 value=int(visible.iloc[len(visible)//2]['분']),format_func=clock)
    current = float(visible.loc[visible['분'].eq(selected),'혼잡도'].iloc[0])
    best = visible.loc[visible['혼잡도'].idxmin()]
    st.subheader(f'{line} {station} · {direction} · {day}')
    st.caption('2026년 9월 기준 · 각 시각부터 30분간의 열차 평균 · 동률이면 이른 시간 표시')
    a,b,c = st.columns(3)
    a.metric(f'{clock(selected)} 혼잡도', f'{current:.1f}%')
    b.metric('범위 내 가장 여유로운 시간',clock(best['분']),f"{best['혼잡도']:.1f}%")
    c.metric('선택 시간 대비 감소 폭',f"{current-best['혼잡도']:.1f}%p")
    local['시각'] = local['분'].map(clock)
    st.subheader('하루 동안의 혼잡 변화')
    chart(px.line(local,x='시각',y='혼잡도',markers=True,labels={'혼잡도':'혼잡도 (%)'}),'network_curve')
    left,right = st.columns([1,1])
    with left:
        st.subheader('30분 앞뒤로 비교')
        nearby = local[local['분'].isin([selected-30,selected,selected+30])]
        chart(px.bar(nearby,x='시각',y='혼잡도',text_auto='.1f',labels={'혼잡도':'혼잡도 (%)'}),'nearby')
    with right:
        st.subheader('같은 시간의 역별 혼잡도')
        rank = subset[subset['분'].eq(selected)].dropna(subset=['혼잡도']).nlargest(10,'혼잡도').sort_values('혼잡도')
        chart(px.bar(rank,x='혼잡도',y='역명',orientation='h',labels={'혼잡도':'혼잡도 (%)'}),'ranking')
    st.subheader('역과 시간대를 함께 비교')
    heatmap(subset[subset['분'].between(*window)],'역명','혼잡도','network_heat','역')
    download(local,'network_selection.csv')
else:
    st.sidebar.caption(f"관측 기간 {meta['date_start']} ~ {meta['date_end']}")
    station = st.sidebar.selectbox('현재역',sorted(cars['현재역'].unique()))
    subset = cars[cars['현재역'].eq(station)]
    next_station = st.sidebar.selectbox('다음역 (운행 방향)',sorted(subset['다음역'].unique()))
    subset = subset[subset['다음역'].eq(next_station)]
    day = st.sidebar.selectbox('요일 유형',sorted(subset['요일구분'].unique()))
    subset = subset[subset['요일구분'].eq(day)].copy()
    dates = sorted(subset['운행일자'].unique())
    date_range = st.sidebar.select_slider('관측 날짜 범위',options=dates,value=(dates[0],dates[-1]))
    subset = subset[subset['운행일자'].astype(str).between(*date_range)]
    minimum = st.sidebar.slider('추천에 필요한 최소 관측일',1,len(dates),min(3,len(dates)))
    subset['일평균'] = subset['혼잡도합']/subset['관측수']
    summary = subset.groupby(['분','호차'],as_index=False,observed=True).agg(혼잡도=('일평균','mean'),관측일수=('운행일자','nunique'),관측수=('관측수','sum'))
    times = sorted(summary['분'].unique().tolist())
    morning = [x for x in times if 420 <= x <= 570]
    default = (morning[0],morning[-1]) if morning else (times[0],times[-1])
    window = st.sidebar.select_slider('탑승 가능한 시간 범위', options=times,value=default,format_func=clock)
    visible = summary[summary['분'].between(*window)].copy()
    st.subheader(f'4호선 {station} → {next_station} · {day}')
    st.caption('신조 전동차 관측자료 · 30분 구간별 날짜 평균 · 칸별 색상은 상대적인 혼잡 크기를 표현')
    eligible = visible[visible['관측일수'].ge(minimum)]
    if eligible.empty:
        st.info('최소 관측일 조건을 만족하는 조합이 없습니다. 기간을 늘리거나 최소 관측일을 낮춰주세요.')
    else:
        best = eligible.sort_values(['혼잡도','분','호차']).iloc[0]
        a,b,c = st.columns(3)
        a.metric('범위 내 최소 혼잡 조합',f"{clock(best['분'])} · {int(best['호차'])}호차")
        b.metric('해당 조합 평균 혼잡도',f"{best['혼잡도']:.1f}%")
        c.metric('해당 조합 관측일',f"{int(best['관측일수'])}일")
    visible_times = sorted(visible['분'].unique().tolist())
    context = (station,next_station,day,date_range,window)
    if st.session_state.get('play_context') != context:
        st.session_state.play_context = context
        st.session_state.play_time = visible_times[0]
        st.session_state.playing = False
    baseline_car = st.selectbox('기준 호차',list(range(1,11)),index=4)
    playing = st.toggle('시간 자동 재생',key='playing')

    @st.fragment(run_every=1.5 if playing else None)
    def car_player():
        if playing:
            pos = visible_times.index(st.session_state.play_time)
            st.session_state.play_time = visible_times[(pos+1) % len(visible_times)]
        selected = st.select_slider('표시 시간', options=visible_times,format_func=clock,key='play_time')
        now = visible[visible['분'].eq(selected)].set_index('호차').reindex(range(1,11))
        cards = []
        for car,row in now.iterrows():
            valid = pd.notna(row['혼잡도'])
            value = float(row['혼잡도']) if valid else 0
            color = '#e9edf2' if not valid else COLORS[min(int(value//50),4)]
            text = f'{value:.1f}%' if valid else '관측 없음'
            count = f"{int(row['관측일수'])}일" if valid else ''
            cards.append(f'<div style="background:{color};padding:14px 8px;border-radius:12px;text-align:center;min-width:85px;color:#152d3b"><b>{car}호차</b><br>{text}<br><small>{count}</small></div>')
        st.markdown('<div style="display:flex;gap:7px;overflow-x:auto;padding:8px 0">'+''.join(cards)+'</div>',unsafe_allow_html=True)
        st.caption(f'{clock(selected)} ~ {clock(selected+30)} · 회색은 해당 시간의 관측 없음 · 과거 평균 패턴 재생')
        baseline = now.loc[baseline_car]
        if pd.notna(baseline['혼잡도']) and baseline['관측일수'] >= minimum:
            same_time = now[now['관측일수'].ge(minimum)].dropna(subset=['혼잡도'])
            best_car = same_time['혼잡도'].idxmin()
            earlier = summary[(summary['분'].eq(selected-30)) & (summary['호차'].eq(baseline_car)) & (summary['관측일수'].ge(minimum))]
            first,second = st.columns(2)
            first.metric(f'{baseline_car}호차 → {best_car}호차 변경 시 감소 폭', f"{baseline['혼잡도']-same_time.loc[best_car,'혼잡도']:.1f}%p")
            if earlier.empty:
                second.metric('같은 칸에서 30분 앞당길 때', '자료 부족')
            else:
                second.metric('같은 칸에서 30분 앞당길 때 감소 폭', f"{baseline['혼잡도']-earlier.iloc[0]['혼잡도']:.1f}%p")
            st.caption('양수는 평균 혼잡도 감소, 음수는 증가입니다. 조건별 관측 날짜가 다를 수 있습니다.')
        else:
            st.caption('기준 호차의 관측일이 부족해 변경 효과를 표시할 수 없습니다.')

        plot = now.reset_index().dropna(subset=['혼잡도'])
        chart(px.bar(plot,x='호차',y='혼잡도',text_auto='.1f',hover_data=['관측일수','관측수'],range_y=[0,max(10,float(visible['혼잡도'].max())*1.1)],labels={'혼잡도':'혼잡도 (%)'}),'car_bars')
    car_player()
    st.subheader('시간대별로 여유로운 칸 찾기')
    heatmap(visible,'호차','혼잡도','car_heat','호차')
    selected_cars = st.multiselect('변화를 비교할 호차',list(range(1,11)),default=[1,5,10])
    index = pd.MultiIndex.from_product([visible_times,selected_cars],names=['분','호차'])
    curves = visible.set_index(['분','호차']).reindex(index).reset_index()
    curves['시각'] = curves['분'].map(clock)
    curves['호차'] = curves['호차'].astype(str)+'호차'
    chart(px.line(curves,x='시각',y='혼잡도',color='호차',markers=True,hover_data=['관측일수'],labels={'혼잡도':'혼잡도 (%)'}),'car_curves')
    st.caption('추천은 선택 기간의 평균 최소값입니다. 관측일수가 적은 조합의 결과는 표본에 민감합니다.')
    visible['시간대'] = visible['분'].map(clock)
    download(visible,'line4_selection.csv')

"""Rebuild deployable aggregates from the two supplied source files."""
import argparse
import io
import json
import re
import zipfile
from pathlib import Path
import pandas as pd


def prepare(source, output):
    output.mkdir(parents=True, exist_ok=True)
    csv = next(source.glob('*지하철혼잡도정보*.csv'))
    base = pd.read_csv(csv, encoding='cp949')
    names = base[['역명','역번호']].drop_duplicates()
    repeated = names.loc[names['역명'].duplicated(False),'역명']
    base['역명'] = base.apply(lambda row: f"{row['역명']} (역코드 {row['역번호']})" if row['역명'] in set(repeated) else row['역명'],axis=1)
    long = base.melt(id_vars=list(base.columns[:5]), var_name='시간', value_name='혼잡도')
    def minute(label):
        h, m = map(int, re.findall(r'\d+', label))
        return (h + (24 if h < 3 else 0)) * 60 + m
    long['분'] = long['시간'].map(minute)
    long.to_csv(output / 'network.csv.gz', index=False, compression='gzip')
    source_zip = next(source.glob('*.zip'))
    pieces = []
    raw_count = duplicates = invalid = 0
    with zipfile.ZipFile(source_zip) as outer:
        for item in outer.infolist():
            if not item.filename.endswith('.zip'):
                continue
            with zipfile.ZipFile(io.BytesIO(outer.read(item))) as inner:
                for name in inner.namelist():
                    if not name.endswith('.csv'):
                        continue
                    frame = pd.read_csv(inner.open(name), encoding='utf-8-sig')
                    raw_count += len(frame)
                    before = len(frame)
                    frame = frame.drop_duplicates()
                    duplicates += before - len(frame)
                    frame['혼잡도'] = pd.to_numeric(frame['혼잡도'].astype(str).str.rstrip('%'), errors='coerce')
                    before = len(frame)
                    frame = frame.dropna(subset=['운행일자','측정시각','현재역','다음역','호차','혼잡도'])
                    frame = frame[frame['혼잡도'].ge(0) & frame['호차'].between(1,10)]
                    invalid += before - len(frame)
                    t = pd.to_timedelta(frame['측정시각']).dt.total_seconds() // 60
                    frame['분'] = ((t.where(t.ge(180), t + 1440) // 30) * 30).astype(int)
                    keys = ['운행일자','요일구분','현재역','다음역','분','호차']
                    daily = frame.groupby(keys, as_index=False).agg(혼잡도합=('혼잡도','sum'), 관측수=('혼잡도','size'))
                    pieces.append(daily)
    daily = pd.concat(pieces).groupby(keys, as_index=False)[['혼잡도합','관측수']].sum()
    for column in ['운행일자','요일구분','현재역','다음역']:
        daily[column] = daily[column].astype('category')
    daily.to_parquet(output / 'cars_daily.parquet', index=False)
    metadata = dict(raw_rows=raw_count, exact_duplicates_removed=duplicates, invalid_rows_removed=invalid,
                    aggregate_rows=len(daily), date_start=min(daily['운행일자'].astype(str)), date_end=max(daily['운행일자'].astype(str)),
                    stations=int(daily['현재역'].nunique()), day_types=sorted(daily['요일구분'].unique().tolist()),
                    network_rows=len(base), network_lines=sorted(base['호선'].unique().tolist()),
                    source_network=csv.name, source_cars=source_zip.name)
    (output/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(metadata,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'data')
    args = parser.parse_args()
    prepare(args.source,args.output)

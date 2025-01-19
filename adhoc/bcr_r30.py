import bar_chart_race as bcr
import pandas as pd
from pathlib import Path

path_data_file = Path("C:/tmp/r30.csv")

pd_tick_data = pd.read_csv(path_data_file)

pd_tick_pivot = pd_tick_data.pivot(
    columns=["Name"],
    index="Tick",
    values=["Land"]
)["Land"].reset_index().set_index("Tick").fillna(0.0)

pd_tick_minimal = pd_tick_pivot.loc[
    lambda df: df.index % 40 == 0
]

bcr.bar_chart_race(
    df=pd_tick_pivot,
    filename='C:/tmp/r30_bcr2.mp4',
    orientation='h',
    sort='desc',
    n_bars=10,
    fixed_order=False,
    fixed_max=False,
    steps_per_period=10,
    interpolate_period=False,
    label_bars=True,
    bar_size=.9,
    period_label={'x': .99, 'y': .15, 'ha': 'right', 'va': 'center'},
    period_fmt='Tick: {x}',
    period_summary_func=lambda v, r: {'x': .99, 'y': .08,
                                      's': f'Total land:\n{v.sum():,.0f}',
                                      'ha': 'right', 'size': 8, 'family': 'Courier New'},
    # perpendicular_bar_func='median',
    period_length=500,
    figsize=(8, 5),
    dpi=600,
    cmap='dark12',
    title='NK R30 Land Race',
    title_size='',
    bar_label_size=7,
    tick_label_size=7,
    shared_fontdict={'family' : 'Courier New', 'color' : '.1'},
    scale='linear',
    writer=None,
    fig=None,
    bar_kwargs={'alpha': .7},
    filter_column_colors=False) 
    
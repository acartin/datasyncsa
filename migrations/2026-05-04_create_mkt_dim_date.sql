begin;

create table if not exists public.mkt_dim_date (
  date_key integer primary key,
  calendar_date date not null unique,
  year smallint not null,
  quarter smallint not null,
  month smallint not null,
  day smallint not null,
  week_of_year smallint not null,
  day_name varchar(20) not null,
  month_name varchar(20) not null,
  is_weekend boolean not null
);

comment on table public.mkt_dim_date is
  'Dimension calendario para analitica de market/pricing snapshots.';

comment on column public.mkt_dim_date.date_key is
  'Clave entera en formato YYYYMMDD.';

insert into public.mkt_dim_date (
  date_key,
  calendar_date,
  year,
  quarter,
  month,
  day,
  week_of_year,
  day_name,
  month_name,
  is_weekend
)
select
  to_char(d::date, 'YYYYMMDD')::integer as date_key,
  d::date as calendar_date,
  extract(year from d)::smallint as year,
  extract(quarter from d)::smallint as quarter,
  extract(month from d)::smallint as month,
  extract(day from d)::smallint as day,
  extract(week from d)::smallint as week_of_year,
  trim(to_char(d, 'Day')) as day_name,
  trim(to_char(d, 'Month')) as month_name,
  extract(isodow from d) in (6, 7) as is_weekend
from generate_series(
  date '2020-01-01',
  date '2035-12-31',
  interval '1 day'
) as d
on conflict (date_key) do update
set
  calendar_date = excluded.calendar_date,
  year = excluded.year,
  quarter = excluded.quarter,
  month = excluded.month,
  day = excluded.day,
  week_of_year = excluded.week_of_year,
  day_name = excluded.day_name,
  month_name = excluded.month_name,
  is_weekend = excluded.is_weekend;

commit;

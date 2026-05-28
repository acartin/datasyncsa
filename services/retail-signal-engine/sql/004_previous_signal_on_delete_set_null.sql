alter table public.mkt_client_signal
  drop constraint if exists fk_mkt_client_signal_previous;

alter table public.mkt_client_signal
  add constraint fk_mkt_client_signal_previous
  foreign key (previous_client_signal_id)
  references public.mkt_client_signal(client_signal_id)
  on delete set null;

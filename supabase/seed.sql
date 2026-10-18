-- Local/dev seed data, applied by `supabase db reset` after all migrations.
-- Never runs against staging or production.

-- A handful of real road shoes so the upload form and catalogue have something to show.
-- `year` is the model's approximate launch year; good enough for development data.
-- Wide variants are separate models because the shoe (last) itself differs.
insert into public.shoe_models (brand, model, year) values
  ('Shimano', 'S-Phyre RC903', 2022),
  ('Shimano', 'RC7', 2020),
  ('Shimano', 'RC7 Wide', 2020),
  ('Specialized', 'S-Works Ares', 2020),
  ('Specialized', 'S-Works 7', 2019),
  ('Sidi', 'Wire 2', 2018),
  ('Giro', 'Imperial', 2018),
  ('Fizik', 'Vento Infinito Carbon 2', 2020),
  ('Lake', 'CX241', 2018),
  ('Northwave', 'Extreme Pro 3', 2023);

-- Chạy trong Supabase Dashboard -> SQL Editor

create table if not exists posts (
    id text primary key,
    platform text not null default 'reddit',
    subreddit text not null,
    title text,
    selftext text,
    author text,
    url text,
    created_utc double precision,
    collected_at double precision,
    score integer default 0,
    num_comments integer default 0,
    upvote_ratio double precision default 0,
    pain_score double precision default 0,
    matched_keywords text,
    query text,
    comments text,
    inserted_at timestamptz default now()
);

create index if not exists idx_posts_platform on posts(platform);
create index if not exists idx_posts_pain on posts(pain_score desc);
create index if not exists idx_posts_collected on posts(collected_at desc);

alter table posts enable row level security;

drop policy if exists "public read posts" on posts;
create policy "public read posts" on posts
    for select to anon using (true);

create table if not exists repo_stars (
    full_name text not null,
    stars integer not null,
    captured_at double precision not null,
    primary key (full_name, captured_at)
);

alter table repo_stars enable row level security;

drop policy if exists "public read repo_stars" on repo_stars;
create policy "public read repo_stars" on repo_stars
    for select to anon using (true);

create table if not exists repo_meta (
    full_name text primary key,
    description text,
    language text,
    url text
);

alter table repo_meta enable row level security;

drop policy if exists "public read repo_meta" on repo_meta;
create policy "public read repo_meta" on repo_meta
    for select to anon using (true);

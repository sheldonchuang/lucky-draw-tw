-- ============================================================================
-- LuckyGo 社群贈券牆 (CouponShare 模式) — Supabase 免費方案完整資料庫結構
-- 執行方式：登入 Supabase Dashboard -> SQL Editor -> 貼上全文執行即可
-- ============================================================================

-- 1. 使用者公開檔案與貢獻值積分
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '好心網友',
  avatar_url text,
  contribution_score integer not null default 0,
  daily_claim_count integer not null default 0,
  last_claim_date date,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "公開讀取使用者基本資料與貢獻值"
  on public.profiles for select
  using (true);

create policy "使用者可更新自己的暱稱"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- 新會員註冊（Google / Email 登入）時自動建立 Profile
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, display_name, avatar_url)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1), '好心網友'),
    new.raw_user_meta_data->>'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- 2. 公開票券清單（不含機密序號與條碼圖片，確保安全）
create table if not exists public.coupons (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  brand text not null,
  title text not null,
  description text default '',
  coupon_type text not null default 'gift' check (coupon_type in ('gift', 'exchange')),
  wanted_note text default '',
  expiry_date date not null,
  status text not null default 'open' check (status in ('open', 'claimed', 'cancelled')),
  claimed_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);

alter table public.coupons enable row level security;

create policy "任何人皆可瀏覽開放中的票券或自己相關票券"
  on public.coupons for select
  using (status = 'open' or auth.uid() = owner_id or auth.uid() = claimed_by);

create policy "登入會員可發布票券"
  on public.coupons for insert
  with check (auth.uid() = owner_id);

create policy "分享者可下架自己的票券"
  on public.coupons for update
  using (auth.uid() = owner_id)
  with check (auth.uid() = owner_id);

-- 3. 票券機密內容表（序號／兌換連結／條碼路徑）— 僅分享者與核准得主可讀！
create table if not exists public.coupon_secrets (
  coupon_id uuid primary key references public.coupons(id) on delete cascade,
  secret_code text default '',
  image_path text default '',
  created_at timestamptz not null default now()
);

alter table public.coupon_secrets enable row level security;

create policy "僅分享者與核准領取者可查看序號與條碼"
  on public.coupon_secrets for select
  using (
    exists (
      select 1 from public.coupons c
      where c.id = coupon_id
        and (c.owner_id = auth.uid() or c.claimed_by = auth.uid())
    )
  );

create policy "僅分享者可寫入票券機密"
  on public.coupon_secrets for insert
  with check (
    exists (
      select 1 from public.coupons c
      where c.id = coupon_id and c.owner_id = auth.uid()
    )
  );

-- 4. 申請領取紀錄表
create table if not exists public.coupon_requests (
  id uuid primary key default gen_random_uuid(),
  coupon_id uuid not null references public.coupons(id) on delete cascade,
  requester_id uuid not null references public.profiles(id) on delete cascade,
  message text not null default '希望能領取使用，謝謝分享！',
  status text not null default 'pending' check (status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  unique (coupon_id, requester_id)
);

alter table public.coupon_requests enable row level security;

create policy "申請者與分享者可查看申請紀錄"
  on public.coupon_requests for select
  using (
    auth.uid() = requester_id
    or exists (
      select 1 from public.coupons c
      where c.id = coupon_id and c.owner_id = auth.uid()
    )
  );

create policy "登入會員可送出領取申請（不可申請自己的券）"
  on public.coupon_requests for insert
  with check (
    auth.uid() = requester_id
    and exists (
      select 1 from public.coupons c
      where c.id = coupon_id and c.status = 'open' and c.owner_id <> auth.uid()
    )
  );

-- 5. 原子化核准發券函式（含每日領券上限 3 張與貢獻值 +1）
create or replace function public.approve_coupon_request(target_request_id uuid)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
  v_req public.coupon_requests%rowtype;
  v_coupon public.coupons%rowtype;
  v_requester public.profiles%rowtype;
  v_today date := (now() at time zone 'Asia/Taipei')::date;
begin
  select * into v_req from public.coupon_requests where id = target_request_id;
  if not found then
    raise exception '找不到此申請紀錄';
  end if;

  select * into v_coupon from public.coupons where id = v_req.coupon_id for update;
  if not found or v_coupon.owner_id <> auth.uid() then
    raise exception '無權限操作此票券';
  end if;

  if v_coupon.status <> 'open' then
    raise exception '此票券已被領取或已下架';
  end if;

  -- 檢查申請者今日領取上限（每日最多 3 張，防囤積）
  select * into v_requester from public.profiles where id = v_req.requester_id for update;
  if v_requester.last_claim_date = v_today and v_requester.daily_claim_count >= 3 then
    raise exception '對方今日領券已達上限（每日最多 3 張）';
  end if;

  -- 更新票券為已領取
  update public.coupons
  set status = 'claimed', claimed_by = v_req.requester_id
  where id = v_coupon.id;

  -- 核准選中申請，拒絕其餘申請
  update public.coupon_requests set status = 'approved' where id = v_req.id;
  update public.coupon_requests set status = 'rejected'
  where coupon_id = v_coupon.id and id <> v_req.id;

  -- 分享者貢獻值 +1
  update public.profiles
  set contribution_score = contribution_score + 1
  where id = v_coupon.owner_id;

  -- 領取者今日次數 +1
  update public.profiles
  set
    daily_claim_count = case when last_claim_date = v_today then daily_claim_count + 1 else 1 end,
    last_claim_date = v_today
  where id = v_req.requester_id;
end;
$$;

-- 5b. 站長專屬會員管理 RPC（僅限站長 Email 呼叫：調整貢獻值或重設今日領券次數）
create or replace function public.admin_update_member(
  target_user_id uuid,
  score_delta integer default 0,
  reset_daily_claim boolean default false
)
returns void
language plpgsql
security definer set search_path = public
as $$
declare
  v_email text := lower(coalesce(auth.jwt()->>'email', ''));
begin
  if v_email <> 'sheldonchuang@gmail.com' then
    raise exception '僅限站長帳號執行此操作';
  end if;

  update public.profiles
  set
    contribution_score = greatest(0, contribution_score + coalesce(score_delta, 0)),
    daily_claim_count = case when reset_daily_claim then 0 else daily_claim_count end
  where id = target_user_id;
end;
$$;

-- 6. 條碼截圖私有儲存空間 (Storage Bucket)
insert into storage.buckets (id, name, public)
values ('coupon-barcodes', 'coupon-barcodes', false)
on conflict (id) do nothing;

create policy "登入會員可上傳自己的票券條碼"
  on storage.objects for insert
  with check (bucket_id = 'coupon-barcodes' and auth.role() = 'authenticated');

create policy "僅分享者與核准領取者可讀取條碼圖片"
  on storage.objects for select
  using (
    bucket_id = 'coupon-barcodes'
    and exists (
      select 1 from public.coupon_secrets s
      join public.coupons c on c.id = s.coupon_id
      where s.image_path = name
        and (c.owner_id = auth.uid() or c.claimed_by = auth.uid())
    )
  );

-- ============================================================================
-- 7. 社群開獎結果回報表（學獎一下：網友回報中獎名單連結＋站長審核）
-- ============================================================================
create table if not exists public.lottery_results (
  id uuid primary key default gen_random_uuid(),
  event_id text not null,
  event_title text not null default '',
  reporter_id uuid not null references public.profiles(id) on delete cascade,
  result_url text not null,
  note text default '',
  status text not null default 'pending' check (status in ('pending', 'verified', 'rejected')),
  created_at timestamptz not null default now()
);

alter table public.lottery_results enable row level security;

create policy "公開讀取已核准開獎結果，站長與回報者可讀待審紀錄"
  on public.lottery_results for select
  using (
    status = 'verified'
    or auth.uid() = reporter_id
    or lower(coalesce(auth.jwt()->>'email', '')) = 'sheldonchuang@gmail.com'
  );

create policy "登入會員可回報開獎結果"
  on public.lottery_results for insert
  with check (auth.uid() = reporter_id);

create policy "僅站長可審核開獎結果狀態"
  on public.lottery_results for update
  using (lower(coalesce(auth.jwt()->>'email', '')) = 'sheldonchuang@gmail.com')
  with check (lower(coalesce(auth.jwt()->>'email', '')) = 'sheldonchuang@gmail.com');

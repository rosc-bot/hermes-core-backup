# Telegram 机器人数据库并发防重与偏唯一索引实战规范

在开发各类资源投稿、抢单、签到或批量收录型 Telegram 机器人时，数据库层的高并发防重与事务隔离设计至关重要。

---

## 一、PostgreSQL 偏唯一索引 (Partial Unique Index) 与 NULL 陷阱

### 1. NULL 语义陷阱
在标准 SQL 与 PostgreSQL 默认唯一索引语义下，`NULL != NULL`。
如果一张表同时包含**多集剧集**（`season`, `episode` 均为整数）和**单部电影**（`season = NULL`, `episode = NULL`），**绝对不能**只用一个联合唯一约束 `UNIQUE(task_id, season, episode)` 来同时防重！
因为 `(task_id, NULL, NULL)` 可以被无限制重复插入而不触发任何唯一冲突。

### 2. 解决方案：双独立 Partial Unique Index
必须在数据库中拆分为两条互斥的偏索引：

```sql
-- 1. 剧集 / 动漫唯一防重（排除 NULL 干扰）
CREATE UNIQUE INDEX uq_resources_episode_accepted
ON resources (task_id, season, episode)
WHERE status = 'ACCEPTED' AND season IS NOT NULL;

-- 2. 电影独立唯一防重（专防 NULL 场景重复收录）
CREATE UNIQUE INDEX uq_resources_movie_accepted
ON resources (task_id)
WHERE status = 'ACCEPTED' AND season IS NULL;
```

---

## 二、批量提交的局部成功与 SAVEPOINT 模式

### 1. 业务场景
用户批量提交 `E15-E18` 时，如果 `E15` 在提交瞬间已被其他并发用户抢先收录（或存在单集冲突）：
- **禁止**：将整批 `E15-E18` 作为一个不可分割的大事务进行全部 rollback；
- **正确做法**：采用 `SAVEPOINT`（SQLAlchemy 的 `async with db.begin_nested():`）逐集独立尝试写入。

```python
# SQLAlchemy 2.0 Async 示例
for ep in declared_episodes:
    try:
        async with db.begin_nested(): # 开启 SAVEPOINT
            res = Resource(
                submission_group_id=group_id,
                task_id=task_id,
                season=season,
                episode=ep,
                status="ACCEPTED",
            )
            db.add(res)
            await db.flush()
        accepted_episodes.append(ep)
    except IntegrityError: # 捕获唯一索引冲突
        conflict_episodes.append(ep)
        res_conflict = Resource(
            submission_group_id=group_id,
            task_id=task_id,
            season=season,
            episode=ep,
            status="REJECTED",
            reject_reason=f"E{ep} 并发冲突：已被抢先收录",
        )
        db.add(res_conflict)

# 外层统一提交成功的记录与冲突日志
await db.commit()
```

---

## 三、真实并发测试编写规范

在编写 pytest 自动化测试时，**严禁**仅用同一个 Session 顺序执行两次 `insert` 来代替并发测试。
必须创建两个独立的 Database Engine 与 Session，使用 `asyncio.gather` 真正并发触发：

```python
@pytest.mark.asyncio
async def test_real_concurrency():
    engine1 = create_async_engine(DB_URL)
    engine2 = create_async_engine(DB_URL)
    session_maker1 = async_sessionmaker(bind=engine1)
    session_maker2 = async_sessionmaker(bind=engine2)

    async def submit_a():
        async with session_maker1() as s:
            return await process_submission(s, ...)

    async def submit_b():
        async with session_maker2() as s:
            return await process_submission(s, ...)

    results = await asyncio.gather(submit_a(), submit_b())
    # 断言最终数据库严格只有 1 条 ACCEPTED
    ...
    await engine1.dispose()
    await engine2.dispose()
```

---

## 四、多网盘统一收录与多频道专属路由分流 (Multi-Channel Dedicated Routing)

### 1. 业务场景
机器人支持多种网盘投稿（如光鸭、移动、夸克、阿里等），但在 Telegram 运营中，经常需要将不同网盘的资源分别推送到各自对应的专属频道（例如：频道 A 专收光鸭资源，频道 B 专收移动云盘资源）。

### 2. 数据库驱动的动态路由设计
- **配置表扩展**：在 `cloud_configs` 表中增加 `channel_id` 字段（如 `guangya` 绑定 `-1004387965244`，`mobile` 绑定 `-1004410413711`，未分配频道的网盘设为 `NULL`）。
- **入库与推送解耦**：用户投稿任意受支持的网盘，系统照常执行查重、判缺扣减、积分结算与数据库 ACCEPTED 入库。
- **发布路由层分流**：
  ```python
  target_channel = cloud_cfg.channel_id or settings.CHANNEL_ID
  if not target_channel or target_channel == "-1000000000000":
      logger.info(f"Skipping channel publish: no target channel for {cloud_cfg.name}")
      return False
  
  await bot.send_message(chat_id=target_channel, text=msg_text, parse_mode="HTML")
  ```
  - **光鸭投稿**：精准推送至光鸭专属频道；
  - **移动投稿**：精准推送至移动专属频道；
  - **无专属频道网盘**：只入库记分，不向专有频道乱发消息，确保各个专属频道的 100% 垂直纯净度。
- **推送失败不回滚原则**：
  - Telegram 频道广播如果因 API 限流、网络超时或 Bot 权限不足导致失败；
  - **严禁回滚数据库已 ACCEPTED 的事务或积分**，只需捕获并记录日志。

---

## 五、批次 submission_group_id 与积分安全结算

1. **唯一批次标识**：一次批量投稿（无论包含多少集或电影）必须生成唯一的 `submission_group_id`（如 `grp_xxxx`），同批所有 resource 记录强绑定该 ID。
2. **积分幂等结算**：
   - 基础积分：按 group 结算，同一个 group 只要有 $\ge 1$ 集成功进入 `ACCEPTED`，基础分 +1（禁止按集数重复发分）；全部冲突或失败为 0 分。
   - TMDB 匹配奖励：仅当该条目原本未绑定 TMDB、当前用户首次在交互候选列表中直接选对、且该 group 至少 1 集正式 ACCEPTED 时，额外奖励 +1 分；若条目已有 TMDB 直接复用，则绝不加分。

---

## 六、FSM 状态机用户交互与静默丢弃防呆机制 (Fallback Guidance & Admin Binding)

### 1. 状态机外无感交互陷阱
在多状态（FSM）机器人中，用户经常在未进入指定会话状态（如尚未通过 `/tasks` 选择作品）时，就直接粘贴分享链接或文本。
- **陷阱**：若未配置兜底处理器，框架（如 aiogram）会判定为 `Update is not handled` 静默丢弃，导致用户误以为机器人死机或没收到消息。
- **解决方案**：在路由最末尾挂载 `@router.message(F.text)` 全局兜底 handler。
  ```python
  @router.message(F.text)
  async def fallback_text_handler(message: types.Message, state: FSMContext):
      current_state = await state.get_state()
      if current_state is None:
          await message.answer("💡 收到您的消息啦！目前没有进行中的投稿会话，请先输入 /tasks 选择任务后再发送链接哦~")
  ```

### 2. 多管理员灵活绑定
- 在配置与鉴权函数中支持单个或英文逗号分隔的多管理员 ID：
  ```python
  def is_admin(user_id: int) -> bool:
      admin_ids = [int(x.strip()) for x in str(settings.ADMIN_TG_ID).split(",") if x.strip().isdigit()]
      return user_id in admin_ids
  ```
- 既保障了最高管理权限安全，又方便后续随时扩展审核与任务发布员。

# Fork 协作与同步指南

本文档记录本仓库（fork 自 [datawhalechina/hello-agents](https://github.com/datawhalechina/hello-agents)）的远程配置、SSH 免密设置，以及日常「改自己的代码 + 同步上游更新」的操作流程。

## 1. 仓库关系

| 远程 | 地址 | 用途 | 权限 |
| --- | --- | --- | --- |
| `origin` | `git@github.com:junfuhuang/hello-agents.git` | 自己的 fork，所有推送都走这里 | 读写 |
| `upstream` | `https://github.com/datawhalechina/hello-agents.git` | 原项目，只用来拉取更新 | 只读 |

- `main` 分支追踪 `upstream/main`，因此 `git pull` = 拉取原项目最新代码。
- `remote.pushDefault = origin`，因此 `git push` 默认推送到自己的 fork，不会误推原项目。
- `upstream` 的 pushurl 被显式设为 `no_push`，即使手滑执行 `git push upstream` 也会被拒绝。

## 2. 已完成的配置

### 2.1 远程与分支

```bash
git clone https://github.com/junfuhuang/hello-agents.git
cd hello-agents

git remote add upstream https://github.com/datawhalechina/hello-agents.git
git fetch upstream
git branch --set-upstream-to=upstream/main main     # pull 拉上游
git config remote.pushDefault origin               # push 推自己的 fork
git config pull.rebase false                       # 同步用 merge，保留合并记录
git remote set-url --push upstream no_push         # 禁止推送到原项目
```

### 2.2 同步别名

```bash
git config alias.sync '!git fetch upstream && git merge upstream/main'
git config alias.upstream-log '!git fetch upstream && git log --oneline HEAD..upstream/main'
```

- `git sync`：拉取并合并上游更新。
- `git upstream-log`：先看看上游比我多了哪些提交。

### 2.3 SSH 免密（443 端口）

服务器屏蔽了 SSH 22 端口，GitHub 的 SSH 走 443：

`~/.ssh/config`：

```
Host github.com
    HostName ssh.github.com
    Port 443
    User git
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

密钥生成与验证：

```bash
ssh-keygen -t ed25519 -C "junfuhuang@tencent.com" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub      # 添加到 GitHub → Settings → SSH and GPG keys
ssh -T git@github.com          # 看到 Hi junfuhuang! 即成功
git remote set-url origin git@github.com:junfuhuang/hello-agents.git
```

## 3. 日常操作

### 分支纪律（重要）

| 分支 | 职责 | 能否直接 commit |
| --- | --- | --- |
| `main` | 只做同步，始终与 `upstream/main` 保持一致 | ❌ 禁止 |
| `feat/xxx`、`docs/xxx` | 自己的开发分支，基于 `upstream/main` 创建 | ✅ |

不在 `main` 上直接提交的原因：

1. `main` 里混入自己的提交后，从它开分支提 PR 会把无关提交算进 diff。
2. `main` 追踪 `upstream/main`，自己的改动与上游更新在同一条线上，同步时更容易冲突。
3. 上游通常以 squash 方式合并 PR，本地 `main` 上留着原始提交，`git pull` 拉回 squash 版本时同一改动出现两个不同 hash，容易冲突。

### 标准流程

```bash
# 同步上游最新代码到本地（main 只做这一件事）
git switch main && git pull

# 基于上游最新创建开发分支，保证 PR 差异干净
git switch -c feat/xxx upstream/main
git add . && git commit -m "feat: xxx"
git push -u origin feat/xxx     # 推到自己的 fork

# 开发期间上游有更新时，把更新合并进开发分支
git switch main && git pull
git switch feat/xxx && git merge main

# 向原项目贡献：在 GitHub 网页上从 feat/xxx 向 datawhalechina/hello-agents 提 PR
```

建议改动始终放在新分支，不要直接堆在 `main` 上，避免与上游更新冲突。

## 4. 常见问题

| 报错 | 原因 | 解决办法 |
| --- | --- | --- |
| `Password authentication is not supported` | GitHub 自 2021 年起 HTTPS 不支持账号密码 | 改用 SSH，或 HTTPS + Personal Access Token |
| `Permission to xxx denied to junfuhuang (403)` | 凭据身份认证成功但没有写权限 | Classic Token 需勾 `repo`；Fine-grained Token 需 `Contents: Read and write` |
| `kex_exchange_identification: Connection closed` | SSH 22 端口被网络屏蔽 | 按 2.3 配置 `HostName ssh.github.com` + `Port 443` |
| `fatal: not a git repository` | 在仓库外执行 git 命令 | 先 `cd /data/workspace/hello-agents` |
| 命令执行后没有任何输出 | Git 成功静默、失败才报错 | 用 `git remote -v` / `git status -sb` 自行确认 |

清除已缓存的错误凭据：

```bash
printf "protocol=https\nhost=github.com\n" | git credential reject
```

## 5. 本次同步记录

- 克隆时 fork 的 `main` 位于 `f636783`，落后上游 40 个提交，且 fork 上有 1 个上游没有的提交。
- 执行 `git merge upstream/main` 合并全部上游更新（无冲突），本地生成合并提交 `afb6cd9`。
- 通过 SSH 推送：`f636783..afb6cd9  main -> main`。
- 推送后 `origin/main` 与本地 `main` 均为 `afb6cd9`，未推送提交数为 0。
- 此时相对上游 `ahead 2`：fork 独有提交 `f636783` + 合并提交，属正常状态。

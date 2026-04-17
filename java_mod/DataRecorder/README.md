# STS DataRecorder Mod

用于给 Slay the Spire 原版运行过程打日志，作为 Python 复刻项目的 ground truth 输入。

## 当前能力

- 记录 run 基本信息、初始/最终牌组与遗物、终局状态
- 记录 map、`pathTaken`、战斗结果、RNG snapshot / call
- 记录事件点击流 `eventChoices`，并额外产出每层一条的 `eventSummaries`
- 记录卡牌奖励选择，兼容 `pick` / `skip` / `Singing Bowl`
- 记录商店购买、休息点行为、金币/生命变化、药水与遗物获得等辅助数据

## 构建

这是一个 Gradle Java 8 项目，源码位于 [src/main/java/stsrecorder](/c:/Users/HP/Desktop/WarframeBot/Slay%20The%20Spire/java_mod/DataRecorder/src/main/java/stsrecorder)。

推荐命令：

```bash
cd java_mod/DataRecorder
./gradlew jar
```

仓库里也保留了 `build.ps1` / `build.bat` 这类本地脚本，适合你已经固定好 `STS_PATH` / workshop 依赖路径时直接使用。

## 安装

1. 构建 `DataRecorder` jar
2. 把 jar 放进 Slay the Spire 的 `mods` 目录
3. 用 ModTheSpire 启动游戏

## 输出

默认输出目录仍然是：

```text
~/sts_data_logs/
```

日志文件名形如：

```text
run_<seedString>_<timestamp>.json
```

## 关键字段

- 兼容保留：
  - `pathTaken`
  - `cardRewards`
  - `eventChoices`
- 新增可选增强：
  - `runResult`
  - `runResultSource`
  - `endAct`
  - `eventSummaries`
  - `cardRewards[].choiceType`
  - `cardRewards[].notPickedCardIds`

其中：

- `eventChoices` 仍是原始点击流
- `eventSummaries` 是每层最多一条的主事件摘要，优先给 Python harness 使用
- `cardRewards` 现在能表达真实拿牌、`SKIP`、`Singing Bowl`

## 与 Python 侧的关系

- `sts_py/tools/compare_logs.py` 继续兼容旧日志
- `sts_py/tools/ground_truth_harness.py` 会优先消费 `eventSummaries`
- 如果新字段不存在，Python 会自动回退到旧字段逻辑

这意味着旧日志不需要重导出也能继续做基础对照；新日志则能提供更稳定的 floor-level diff 输入。

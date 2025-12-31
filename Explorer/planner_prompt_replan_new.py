# 这是优化后的 replan prompt 构建函数
# 可以直接导入使用，或替换到 planner.py 中

def _build_replan_prompt_optimized(
    planner_self,  # ExplorationPlanner 实例
    target,
    current_plan,
    screen_text,
    last_step,
    last_result,
    navigation_path,
    immediate_screen_text=None,
    feature_tree=None,
    recent_state_sequence=None
):
    """优化后的重新规划Prompt - 结构清晰，加入CoT"""
    
    import re
    
    # 计算下一步编号
    match = re.search(r'step_(\d+)', last_step.step_id)
    next_step_num = int(match.group(1)) + 1 if match else len(current_plan.completed_steps) + 2
    
    # ========== 第1部分：执行上下文 ==========
    prompt = f"""# 应用功能探索 - 重新规划

## 📊 执行上下文

**探索目标**: {target.feature_to_explore}
**当前功能**: {' -> '.join(current_plan.current_feature.get('feature_path', [target.feature_to_explore]))}
**已完成步骤**: {len(current_plan.completed_steps)} 步

### 上一步执行结果
- **步骤**: {last_step.step_id} | {last_step.instruction}
- **结果**: {'✅ 成功' if last_result.get('success', False) else '❌ 失败'} ({last_result.get('execution_time', 0):.1f}秒，{last_result.get('iterations', 1)}次迭代)
- **目标**: {last_step.sub_goal}

---

## 🖼️ 当前屏幕
"""
    
    # ========== 第2部分：屏幕信息 ==========
    if immediate_screen_text:
        prompt += f"""
### 双截图模式
我们提供了两张截图：
1. **立刻截图（0.2秒）**: 捕获快速消失的toast/bubble
2. **稳定截图（5秒）**: 页面完全加载的状态

**立刻截图内容**:
```
{immediate_screen_text}
```

**稳定截图内容**:
```
{screen_text}
```

⚠️ 比较两张截图，关注只在立刻截图出现的提示/错误！
"""
    else:
        prompt += f"""
```
{screen_text}
```
"""
    
    # ========== 第3部分：探索指引 ==========
    tips = planner_self._get_app_specific_tips(target)
    forbidden_note = ""
    if tips and "⚠️" in tips:
        forbidden_note = "\n\n⚠️ **禁止项提醒**: 请严格遵守下方的应用特定禁止事项"
    
    prompt += f"""

---

## 📋 探索指引

### 核心目标
探索 = **发现功能** + **理解结构** + **记录交互**（为测试用例设计提供基础）

### 关键原则
1. ✅ **要做**: 发现按钮、识别功能、理解流程、记录页面结构
2. ❌ **不做**: 边界测试、异常输入、压力测试、重复操作
3. ⚠️ **安全**: 金钱交易→探索到确认页即停，失败2-3次→换路径
4. 📱 **多样**: 点击+滑动+长按组合，避免过度点击{forbidden_note}

{tips}

---

## 🎯 重新规划任务

### ⭐ 思考步骤（CoT - 必须完整包含在plan_thought中）

**第1步：屏幕分析**
- 当前页面是什么？（主页/列表/详情/弹窗...）
- 上一步达到预期了吗？
- 有哪些可交互元素？

**第2步：功能定位**  
- 还在当前功能 `{' -> '.join(current_plan.current_feature.get('feature_path', [target.feature_to_explore]))}` 中吗？
- 如果不在→属于已有子功能/新功能/子子功能？

**第3步：探索策略**
- 当前功能完成度？
- 下一步：继续/切换/返回？

**第4步：步骤规划**
- 下一个原子操作是什么？
- 预期结果？
- 需要几次尝试？

---

## 📝 输出要求

### 步骤粒度 ⚠️ 极其重要
**每个step = 1个原子操作**

✅ 正确:
- step_{next_step_num}: "点击'新建文件夹'按钮"
- step_{next_step_num+1}: "输入'test'"

❌ 错误:
- step_{next_step_num}: "点击新建文件夹按钮，然后输入test"  ← 2个操作！

**原因**: 执行器只在第1个操作后截图，多操作丢失中间状态！

### JSON格式
```json
{{
  "plan_thought": "第1步：屏幕分析... 第2步：功能定位... 第3步：探索策略... 第4步：步骤规划...",
  "overall_plan": "简要整体计划（1-2句话）",
  "feature_update": {{"action": "none", "details": {{}}}},
  "current_feature": {{
    "feature_path": ["{target.feature_to_explore}", "子功能名"],
    "status": "exploring",
    "is_new_feature": false,
    "previous_feature_completed": false
  }},
  "steps": [
    {{
      "step_id": "step_{next_step_num}",
      "instruction": "具体操作（一个原子操作）",
      "sub_goal": "这步的目标",
      "enable_reflection": true,
      "max_iterations": 5
    }}
  ]
}}
```

**注意**:
- `plan_thought` 必须包含完整CoT（第1-4步）
- 步骤从 `step_{next_step_num}` 连续编号
- 虽然可生成多步，实际只执行第1步
- 最多 {planner_self.config.max_plan_steps} 个步骤
"""
    
    return prompt

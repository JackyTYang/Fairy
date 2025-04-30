from Fairy.info_entity import ProgressInfo, ActionInfo, ScreenInfo

user_interaction_situation=[
    "1: The current sub-goal is sensitive or dangerous action and the user has not confirmed it in the 'Instruction'. E.g., file deletion when the user has not instructed file deletion.",
    "2: The current sub-goal is irreversible action and the user has not confirmed it in the 'Instruction'. E.g., a file deletion that requires the user to reconfirm the action before the file is irreversibly deleted. MAKE SURE that the action is indeed irreversible.",
    "3: The next action involves a selection, and the user has not indicated in the 'Instruction' which choice to make. When there are multiple options on the current screen that fulfill the user's instructions, and you want to SELECT a specific option, but the user has not explicitly instructed you to do so, you must interact with the user, and never take matters into your own hands! E.g., there are multiple search results that meet the user's instruction that require further decision-making by the user.",
    "4: The instruction given by the user is ambiguous. E.g., the user asks to make a phone call but does not specify a contact person."
]

replan_steps = [
    "If the 'action result' is A, then: update the 'History Progress Status'; mark the task as completed in the 'Overall Plan'; and determine the next 'Sub-goal' to be executed based on the plan.",
    "If the 'action result' is B, then: update the 'History Progress Status'; outline the 'Sub-goal' that should be continued next.",
    "If the 'action result' is C or D, then: think step-by-step about whether the 'Overall Plan' needs to be revised to address the error; determine the next 'Sub-goal' to be executed based on the plan.",
    "Due to the lack of knowledge you may have when you first plan, please review and update (if necessary) your 'Overall Plan' based on the main features and content of the current screen.",
    "In the following cases where user interaction is required, determine whether user interaction is required next, and select 0 if no user interaction is required:",
    user_interaction_situation,
    "If user interaction is required, the overall plan must be updated to add sub-goals related to user interaction, as well as clarifying the sub-goals that should be accomplished after the interaction."
]

replan_steps_for_usr_chat = [
    "In the following cases where user interaction is required, determine whether user interaction is required next, and select 0 if no user interaction is required:",
    user_interaction_situation,
    "If user interaction is no longer required, think about whether the overall plan, sub-goals that were planned to be executed prior to the interaction need to be changed. \n NOTE that you have just interacted with the user and have not yet actually executed the user's new instructions, in which case you should not change the current subgoal or it will result in skipped execution. (e.g. If the task is to make a selection  and the user has already selected an option, this task is NOT completed! Because the user's decision has not yet been processed by the executor Agent!)"
]

plan_steps = [
    "Summarize and abstract the user's instructions into a generic task, taking care to be abstract and high-level.",
    "Think comprehensively about the steps to accomplish this generic task, being very abstract and high-level.",
    "Check to see if you have missed any key steps.",
    "Based on the thinking you have just done, develop a step-by-step, plan to accomplish the user's instructions. This directive should include multiple sub-goals. The User can only fill in the prompts, not perform any actual actions. Your plan must be rigorous, e.g. When you want 'select' you must indicate the action that follows the selection, e.g. 'select and enter' or 'select and confirm'."
]

plan_output = [
    "plan_thought: Your rationale for developing the plan and sub-goals.",
    "overall_plan: All plans for completion of 'user instruction'. Check to see if any key steps have been missed. The plan consists of ONE or MORE sub-goals, export it as a list.",
    "current_sub_goal: The first sub-goal you should work on."
]

replan_output = [
    "plan_thought: Your rationale for developing or modifying the plan and sub-goals.",
    "overall_plan: All plans for completion of 'user instruction'. Check to see if any key steps have been missed. The plan consists of ONE or MORE sub-goals, export it as a list. If you need to update the plan, provide the updated plan here. Otherwise keep the current plan and copy it here. If user interaction is required, the overall plan must be updated.",
    "current_sub_goal: The sub-goal you should work on. If the current one is complete, pick the next one, otherwise keep it. If all subgoals have been completed, write 'Finished'.",
    "user_interaction_type: Please use 0, 1, 2, 3, and 4 to indicate.",
    "user_interaction_thought: Explain in detail the reason for your choice (explain one by one why it is not 1~4). If your choice is not 0, please add the information you want to get from interacting with users."
]

replan_output_for_usr_chat = [
    replan_output[0],
    replan_output[1],
    "current_sub_goal: In the vast majority of cases, the current sub-goal should be left unchanged because the user has just made a decision to help the current sub-goal execute, and the current sub-goal has not yet been actually executed. Unless you are quite sure that you need to change the current sub-goal (e.g., if the user requests it).",
    replan_output[3],
    replan_output[4]
]

def plan_tips(tips):
    prompt = f"---\n" \
             f"Here's some TIPS for thinking about the plan. These TIPS are VERY IMPORTANT, so MAKE SURE you follow them to the letter: \n" \
             f"IMPORTANT: Your partners include 'ActionDecider', 'UserInteractor' and 'KeyInformationExtractor'. If you set 'user_interaction_type' to 0, it will be left to the 'ActionDecider' to execute your current_sub_goal, otherwise it will be left to the 'UserInteractor' to interact with the user. The 'KeyInformationExtractor' will automatically extract and organize information after a change in screen information without any separate command from you. \n"\
             f"{tips}\n" \
             f"\n"
    return prompt

def screen(current_screen_info: ScreenInfo, non_visual_mode):

    if not non_visual_mode:
        screenshot_prompt = "The attached image is a screenshots of your phone to show the current state."
    else:
        screenshot_prompt = "The following text description (e.g. JSON or XML) is converted from a screenshots of your phone to show the current state."

    prompt = f"---\n"
    prompt += current_screen_info.perception_infos.get_screen_info_note_prompt(screenshot_prompt)  # Call this function to supplement the prompt "Size of the Image and Additional Information".
    prompt += f"\n"

    prompt += f"- Current Page: {current_screen_info.current_activity_info.activity}\n"
    prompt += current_screen_info.perception_infos.get_screen_info_prompt()  # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

    prompt += f"Please scrutinize the above screen information to infer the type of the current page (e.g., home page, search page, results page, details page, etc.) and thus the main function of the page. This helps you to avoid wrong plans." \
          f"\n"
    return prompt

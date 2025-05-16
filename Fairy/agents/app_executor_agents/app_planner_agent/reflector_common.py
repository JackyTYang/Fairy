from loguru import logger

from Fairy.info_entity import ProgressInfo, ActionInfo, ScreenInfo

reflection_steps = [
    "Carefully examine the screenshots and screen information before and after the action provided above to determine which of the following resulted from this action:",
    [
        "A: Successful, with results meeting expectations and fully accomplishing the sub-goal;",
        "B: Partial Successful, where the result was as expected but did not fully accomplish the sub-goal. For example, all options should be selected, but currently only some options are selected;",
        "C: Failure, the result is incorrect and an attempt to fall back to the previous state is required;",
        "D: Failure, the action was executed without producing any screen change."
    ],
    "If the 'action result' is C or D, then: try to explain the 'Error Potential Causes' of the failure;"
]

reflection_output = [
    "action_result: Please use A, B, C, and D to indicate.",
    "error_potential_causes: If the action_result is A or B, please fill in 'None' here. If the action_result is C or D, please describe in detail the error and the potential cause of failure.",
    "progress_status: If the action_result is A or B, update the progress status. If the action_result is C or D, copy the previous progress status."
]

def old_and_new_screen_comparison(previous_screen_info: ScreenInfo, current_screen_info: ScreenInfo, non_visual_mode: bool):
    if not non_visual_mode:
        screenshot_prompt = "The two attached images are two screenshots of your phone before and after your last action to reveal the change in status"
    else:
        screenshot_prompt = "The following two text descriptions (e.g. JSON or XML) are converted from two screenshots of your phone before and after your last action to reveal the change in status"

    prompt = f"---\n"
    prompt += previous_screen_info.perception_infos.get_screen_info_note_prompt(
        screenshot_prompt)  # Call this function to supplement the prompt "Size of the Image and Additional Information".
    prompt += f"\n"

    prompt += f"- Page before the Action: {previous_screen_info.current_activity_info.activity}\n"
    prompt += previous_screen_info.perception_infos.get_screen_info_prompt(
        "before the Action")  # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

    prompt += f"- Page after the Action: {current_screen_info.current_activity_info.activity}\n"
    prompt += current_screen_info.perception_infos.get_screen_info_prompt(
        "after the Action")  # Call this function to get the content of the prompt "Screen Perception Information and Keyboard Status".

    prompt += f"Please scrutinize the above screen information to infer the type of  previous and current pages (e.g., home page, search page, results page, details page, etc.) and thus the main function of these pages. Please carefully identify whether the page has jumped or not! This will help you to find the mistakes in the execution just now and avoid the wrong plan.\n" \
              f"\n"
    return prompt

def is_finished_action(progress_info: ProgressInfo, action_info: ActionInfo) -> bool:
    if progress_info.action_result == "A" and len(action_info.actions) > 0 and action_info.actions[0]['name'] == "Finish":
        logger.bind(log_tag="fairy_sys").info("All requirements in the user's Instruction have been completed.")
        return True
    return False
plan_steps = [
    f"Consider which apps the user's plan will require to collaborate in order to accomplish, and if the apps on the user's phone are truly insufficient to accomplish these actions, consider downloading new apps to do so.",
    "Think comprehensively about the steps to accomplish this task using these apps, at a very high level.",
    "Check to see if any key steps have been missed.",
    "Create a step-by-step plan for completing the user instructions based on the thinking you have just done.",
    [
        "IMPORTANT: The plan consists of one or more tasks, each of which should be performed by a specific app, and for which you need to provide the task instructions and the information that must be gathered about that/those apps.",
        "IMPORTANT: If consecutive steps are completed on the SAME app (app_package_name is SAME), DO NOT split them into multiple tasks.",
        "IMPORTANT: Task descriptions should think like instructions made by the user, please don't do any low-level planning. You should only identify the overall task that the app needs to accomplish and NOT BREAK that overall task down in more detail."
    ]
]

plan_output = [
    "ins_language: Language used for User Instruction. Please use standard language name (e.g. Chinese(中文), English, French(Français), German(Deutsch)).",
    "global_plan_thought: A detailed explanation of your rationale for the plan. Please pay special attention to the contents of the 'NOTE' and check it.",
    "global_plan:  All plans for completion of 'user instruction'. Check to see if any key steps have been missed. The plan consists of ONE or MORE tasks, export it as a list; the tasks should include 3 keys: \n"
    "a. app_package_name: The name of the package of the app that performs the current task (Must be consistent with what is provided in the list); \n"
    "b. instruction: The instruction of the app that performs the current task (a description of what the application needs to accomplish, be careful not to include any specific steps, it needs to be very high level; DO NOT include OPEN / SWITCH specific app in the instruction; For this key only, the language used should be the same as 'ins_language' ); \n"
    f"c. key_info_request: A description of the key information to be obtained. Fill in 'None' if there is no need for any information from this task.",
]


def plan_tips(tips):
    prompt = f"---\n" \
             f"Here's some TIPS for thinking about the plan. These TIPS are VERY IMPORTANT, so MAKE SURE you follow them to the letter: \n" \
             f"IMPORTANT: Your partners include 'ActionDecider', 'UserInteractor' and 'KeyInformationExtractor'. If you set 'user_interaction_type' to 0, it will be left to the 'ActionDecider' to execute your current_sub_goal, otherwise it will be left to the 'UserInteractor' to interact with the user. The 'KeyInformationExtractor' will automatically extract and organize information after a change in screen information without any separate command from you. \n"\
             f"{tips}\n" \
             f"\n"
    return prompt
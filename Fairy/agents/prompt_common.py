
def output_json_object(json_object_keys):
    prompt = f"---\n" \
             f"Please provide a JSON with {len(json_object_keys)} keys, which are interpreted as follows:\n"
    prompt += unordered_list(json_object_keys)
    prompt += f"Make sure this JSON can be loaded correctly by json.load().\n"\
              f"\n"

    return prompt

def unordered_list(ls):
    prompt = ""
    for item in ls:
        prompt += f"- {item}\n"
    return prompt

def ordered_list(ls):
    prompt = ""
    order_id = 1
    for index in range(len(ls)):
        if isinstance(ls[index], list):
            prompt += unordered_list(ls[index])
        else:
            prompt += f"{order_id}. {ls[index]}\n"
            order_id += 1
    return prompt
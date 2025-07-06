from openai import OpenAI

def get_gpt_client(config):
    return OpenAI(api_key=config["openai"]["api_key"])
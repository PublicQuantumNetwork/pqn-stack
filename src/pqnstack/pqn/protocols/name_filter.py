import openai


def is_name_appropriate(name: str) -> bool:
    prompt = f"For the following word or phrase, reply with a 'Y' if the word or phrase is generally acceptable. This includes all numbers, special characters, and words that do not closely resemble, imply, or have connotations of profanity, offensive, derogatory, or inappropriate language. Reply with an 'N' if the word or phrase is clearly a bad word, contains profanity, offensive language, has derogatory implications, could be interpreted as subtly inappropriate, or makes references that could be considered offensive in certain contexts, and NO OTHER TEXT: '{name}'"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an assistant that strictly adheres to instructions."},
                {"role": "user", "content": prompt},
            ],
        )

        reply = response["choices"][0]["message"]["content"].strip()

        return reply == "Y"
    except Exception as e:
        print(f"Error checking name: {e}")
        return False


if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    load_dotenv(".config")
    api_key = os.getenv("OPENAI_API_KEY")
    openai.api_key = api_key

    while True:
        user_input = input("Enter a name to check : ").strip()
        if is_name_appropriate(user_input):
            print(f"The name '{user_input}' is appropriate.")
        else:
            print(f"The name '{user_input}' is not appropriate.")

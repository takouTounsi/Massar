from groq import Groq
from dotenv import load_dotenv
import os


load_dotenv()


client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)



response = client.chat.completions.create(

    model="qwen/qwen3-32b",

    messages=[

        {
        "role":"system",
        "content":
        """
        You are a startup advisor.
        Do not change scores.
        Only explain.
        """
        },


        {
        "role":"user",
        "content":
        """
        Startup diagnosis:

        Market score: 50
        Innovation score: 85
        Main blocker:
        Customer validation

        Explain.
        """
        }

    ]

)



print(
response.choices[0].message.content
)
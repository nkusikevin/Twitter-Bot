from langchain.agents import AgentExecutor, create_react_agent
from langchain.agents.format_scratchpad import format_log_to_str
from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain.tools import Tool
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from datetime import datetime, timedelta
import tweepy
import os
from dotenv import load_dotenv
import time
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("twitter_bot.log"), logging.StreamHandler()],
)


class TwitterBot:
    def __init__(self):
        self.load_environment()
        self.setup_twitter_client()
        self.setup_llm()
        self.setup_agent()
        self.tweet_count = 0
        self.last_tweet_time = datetime.now() - timedelta(days=30)

    def load_environment(self):
        """Load environment variables and validate Twitter credentials."""
        load_dotenv()

        self.required_env_vars = {
            "TWITTER_CONSUMER_KEY": os.getenv("TWITTER_CONSUMER_KEY"),
            "TWITTER_CONSUMER_SECRET": os.getenv("TWITTER_CONSUMER_SECRET"),
            "TWITTER_ACCESS_TOKEN": os.getenv("TWITTER_ACCESS_TOKEN"),
            "TWITTER_ACCESS_TOKEN_SECRET": os.getenv("TWITTER_ACCESS_TOKEN_SECRET"),
        }

        missing_vars = [k for k, v in self.required_env_vars.items() if not v]
        if missing_vars:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )

    def setup_twitter_client(self):
        """Initialize Twitter API client."""
        try:
            self.client = tweepy.Client(
                consumer_key=self.required_env_vars["TWITTER_CONSUMER_KEY"],
                consumer_secret=self.required_env_vars["TWITTER_CONSUMER_SECRET"],
                access_token=self.required_env_vars["TWITTER_ACCESS_TOKEN"],
                access_token_secret=self.required_env_vars[
                    "TWITTER_ACCESS_TOKEN_SECRET"
                ],
            )
            logging.info("Twitter client initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Twitter client: {str(e)}")
            raise

    def setup_llm(self):
        """Initialize the language model."""
        try:
            self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.9)
            logging.info("Language model initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize language model: {str(e)}")
            raise

    def generate_tweet(self, prompt: str) -> str:
        """Generate a tweet using the language model."""
        try:
            response = self.llm.invoke(
                f"""Create a tweet based on this prompt: {prompt}
                Requirements:
                - Must be under 280 characters
                - Aim for a tone that is witty, thought-provoking, and occasionally provocative, similar to Elon Musk.
               - Use concise language and avoid unnecessary filler.
    - Minimize the use of hashtags; focus on impactful ideas.
    - Incorporate relevant emojis to enhance the message where appropriate.
                """
            )
            tweet = response.content.strip()
            if len(tweet) > 280:
                tweet = tweet[:277] + "..."
            return tweet
        except Exception as e:
            logging.error(f"Failed to generate tweet: {str(e)}")
            raise

    def setup_agent(self):
        """Initialize the LangChain agent using the new method."""
        try:
            # Define tools
            tools = [
                Tool(
                    name="Tweet Generator",
                    func=self.generate_tweet,
                    description="Generate a tweet using the language model (max 280 characters)",
                )
            ]

            # Define the prompt template
            prompt = PromptTemplate.from_template(
                """Answer the following questions as best you can. You have access to the following tools:

                {tools}

                Use the following format:

                Question: the input question you must answer
                Thought: you should always think about what to do
                Action: the action to take, should be one of [{tool_names}]
                Action Input: the input to the action
                Observation: the result of the action
                ... (this Thought/Action/Action Input/Observation can repeat N times)
                Thought: I now know the final answer
                Final Answer: the final answer to the original input question

                Begin!

                Question: {input}
                {agent_scratchpad}"""
            )

            # Create the agent
            agent = create_react_agent(llm=self.llm, tools=tools, prompt=prompt)

            # Create the agent executor
            self.agent = AgentExecutor(
                agent=agent, tools=tools, verbose=True, handle_parsing_errors=True
            )

            logging.info("Agent initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize agent: {str(e)}")
            raise

    def post_tweet(self, tweet: str) -> Optional[tweepy.Response]:
        """Post a tweet to Twitter with error handling."""
        try:
            response = self.client.create_tweet(text=tweet)
            logging.info(f"Successfully posted tweet: {tweet}")
            return response
        except Exception as e:
            logging.error(f"Failed to post tweet: {str(e)}")
            raise

    def check_rate_limits(self) -> bool:
        """Check if we're within Twitter's rate limits."""
        if (
            self.tweet_count >= 1500
            and datetime.now().month == self.last_tweet_time.month
        ):
            logging.warning("Monthly tweet limit reached")
            return False
        return True

    def run(self):
        """Main bot execution loop."""
        logging.info("Starting Twitter bot")

        while True:
            try:
                if not self.check_rate_limits():
                    time.sleep(3600)  # Wait an hour before checking again
                    continue

                prompt = input("Enter a prompt for the tweet (or 'quit' to exit): ")

                if prompt.lower() == "quit":
                    logging.info("Bot shutting down")
                    break

                # Generate and post tweet
                result = self.agent.invoke({"input": prompt})
                tweet = result.get("output", "")
                self.post_tweet(tweet)

                # Update rate limiting trackers
                self.last_tweet_time = datetime.now()
                self.tweet_count += 1

                # Wait before next tweet
                time.sleep(3600)  # 1 hour delay

            except KeyboardInterrupt:
                logging.info("Bot stopped by user")
                break
            except Exception as e:
                logging.error(f"An error occurred: {str(e)}")
                time.sleep(60)  # Wait a minute before retrying


if __name__ == "__main__":
    try:
        bot = TwitterBot()
        bot.run()
    except Exception as e:
        logging.critical(f"Fatal error: {str(e)}")
        raise

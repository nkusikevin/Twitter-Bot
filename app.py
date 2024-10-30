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
import json
from typing import Optional, List, Dict

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
        self.current_topics = []
        self.category = ""

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

    def generate_topics(self, category: str, num_topics: int = 10) -> List[str]:
        """Generate tweet topics based on a category."""
        try:
            prompt = f"""Generate exactly {num_topics} engaging tweet topics related to {category}.
            You must respond with only a JSON array of strings, nothing else.
            
            Example of expected format:
            ["Topic 1", "Topic 2", "Topic 3"]"""

            response = self.llm.invoke(prompt)

            # Clean the response content
            content = response.content.strip()
            if not content.startswith("["):
                # If response isn't JSON, try to extract JSON-like content
                import re

                json_match = re.search(r"\[.*\]", content, re.DOTALL)
                if json_match:
                    content = json_match.group(0)
                else:
                    # Fallback: create JSON array from line-by-line content
                    topics = [
                        line.strip().strip('"-')
                        for line in content.split("\n")
                        if line.strip()
                        and not line.strip().startswith("[")
                        and not line.strip().startswith("]")
                    ]
                    return topics[:num_topics]

            topics = json.loads(content)
            logging.info(f"Generated {len(topics)} topics for category: {category}")
            return topics
        except json.JSONDecodeError as e:
            logging.error(f"JSON parsing error: {str(e)}")
            logging.error(f"Raw content: {response.content}")
            # Fallback: return some default topics
            return [
                f"{category} trends 2024",
                f"Latest developments in {category}",
                f"Future of {category}",
                f"How {category} is changing",
                f"{category} best practices",
                f"{category} tips and tricks",
                f"Understanding {category}",
                f"{category} innovations",
                f"{category} challenges",
                f"{category} opportunities",
            ]
        except Exception as e:
            logging.error(f"Failed to generate topics: {str(e)}")
            raise

    def generate_tweet(self, topic: str) -> str:
        """Generate a tweet using the language model."""
        try:
            prompt = f"""Create an engaging tweet about: {topic}
            Context: This is part of a series about {self.category}
            
            Requirements:
            - Must be under 280 characters
            - Should be engaging and natural
            - Avoid hashtag spam
            - Include relevant emojis when appropriate
            - Should feel like part of a coherent social media strategy
            - Can include relevant hashtags (max 2)
            """

            response = self.llm.invoke(prompt)
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
            tools = [
                Tool(
                    name="Tweet Generator",
                    func=self.generate_tweet,
                    description="Generate a tweet using the language model (max 280 characters)",
                )
            ]

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

            agent = create_react_agent(llm=self.llm, tools=tools, prompt=prompt)

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

    def refresh_topics(self):
        """Refresh the topic list when it's empty."""
        if not self.current_topics:
            self.current_topics = self.generate_topics(self.category)
            logging.info(f"Refreshed topics for category: {self.category}")

    def run(self):
        """Main bot execution loop."""
        logging.info("Starting Twitter bot")

        # Get initial category
        self.category = input(
            "Enter a category or theme for your tweets (e.g., 'AI technology', 'fitness tips', 'cooking'): "
        )
        print(f"\nStarting automated tweet generation for category: {self.category}")
        print("(Press Ctrl+C to stop or type 'change category' when prompted)")

        while True:
            try:
                if not self.check_rate_limits():
                    time.sleep(3600)
                    continue

                # Refresh topics if needed
                self.refresh_topics()

                # Get next topic
                current_topic = self.current_topics.pop(0)
                logging.info(f"Using topic: {current_topic}")

                # Generate and post tweet
                tweet = self.generate_tweet(current_topic)
                self.post_tweet(tweet)

                # Update rate limiting trackers
                self.last_tweet_time = datetime.now()
                self.tweet_count += 1

                # Wait before next tweet
                print(
                    f"\nNext tweet in 1 hour. Type 'change category' or press Enter to continue with current category:"
                )
                user_input = input()

                if user_input.lower() == "change category":
                    self.category = input("\nEnter new category: ")
                    self.current_topics = []  # Force topic refresh
                    print(f"\nSwitched to category: {self.category}")

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

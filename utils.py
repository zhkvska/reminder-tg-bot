import os
import json

COMPLETION_MESSAGES = [
    "🌟 Great job today! Keep up this amazing rhythm!",
    "✨ You're crushing it! One day at a time!",
    "🎯 Mission accomplished! See you tomorrow for more success!",
    "💪 You've got this routine down! Fantastic work!",
    "🌈 Another successful day in the books! Proud of you!",
    "⭐ Way to stay on track! You're doing great!",
    "🎉 All done for today! You're making excellent progress!",
    "🌺 Wonderful job following through! Keep this momentum!",
    "🏆 Champion move completing all your tasks!",
    "💫 You're building great habits! Keep going!",
    "🌟 Consistency is key, and you're nailing it!",
    "🎨 Another colorful day of achievements!",
    "🚀 Onwards and upwards! You're doing fantastic!",
    "🌞 Brilliant work today! Tomorrow's another opportunity!",
    "💎 You're a gem at staying consistent!",
    "🎵 That's the rhythm! Keep dancing to success!",
    "🌈 You make it look easy! Great dedication!",
    "⚡ Powerful performance today! Keep shining!",
    "🎪 Another successful show! You're amazing!",
    "🌺 Blooming with success! See you tomorrow!"
]

DATA_FILE = "user_data.json"
DEFAULT_TIMEZONE = "Europe/Kyiv"

def load_user_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"users": {}}
    return {"users": {}}


def save_user_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)


def get_user_data(user_id):
    data = load_user_data()
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "messages": [],
            "timezone": DEFAULT_TIMEZONE,
            "active_day": False,
        }
        save_user_data(data)
    return data["users"][user_id]


def update_user_data(user_id, user_data):
    data = load_user_data()
    data["users"][user_id] = user_data
    save_user_data(data)
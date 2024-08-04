from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import httpx
import asyncio
import json
import os
from datetime import datetime
from urllib.parse import urlparse
import requests
import urllib
import threading
admin_ids = [6253407525]  
ALLOWED_CHAT_ID = -1002167325764


def format_data_rate(kbps):
    if kbps >= 1024**3:  
        return f"{kbps / 1024**3:.1f} TB/s"
    elif kbps >= 1024**2:  
        return f"{kbps / 1024**2:.1f} GB/s"
    elif kbps >= 1024:  
        return f"{kbps / 1024:.1f} MB/s"
    else:  
        return f"{kbps:.1f} KB/s"

def add_user_to_subscribed(user_id):
  try:
      with open("sub_users.json", "r") as file:
          subscribed_users = json.load(file)
  except FileNotFoundError:
      subscribed_users = []
  if user_id not in subscribed_users:
      subscribed_users.append(user_id)
      with open("sub_users.json", "w") as file:
          json.dump(subscribed_users, file)

def save_running_server(user_id, server_name):
  running_servers = load_all_running_servers()
  running_servers[str(user_id)] = server_name
  with open('server_running.json', 'w') as file:
      json.dump(running_servers, file)

def remove_running_server(user_id):
  running_servers = load_all_running_servers()
  if str(user_id) in running_servers:
      del running_servers[str(user_id)]
      with open('server_running.json', 'w') as file:
          json.dump(running_servers, file)

async def show_servers(update: Update, context: ContextTypes.DEFAULT_TYPE, servers, server_type):
  language = load_user_language(update.effective_user.id)
  max_button_length = max(len(server['name']) for server in servers) 
  columns = 1 if max_button_length > 13 else 2
  keyboard = []
  row = []
  for server in servers:
      row.append(InlineKeyboardButton(f"🛡{server['name']}🛡", callback_data=f"{server_type}count_{server['name']}"))
      if len(row) == columns:
          keyboard.append(row)
          row = []
  if row:
      keyboard.append(row)

  back_button = InlineKeyboardButton("<< Back", callback_data="back_to_dstatcount_type")
  keyboard.append([back_button])

  reply_markup = InlineKeyboardMarkup(keyboard)
  
  message_text = "Choose a server to start 📊"

  await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')


def load_running_server(user_id):
  try:
      with open('server_running.json', 'r') as file:
          running_servers = json.load(file)
          return running_servers.get(str(user_id))
  except FileNotFoundError:
      return None

def load_all_running_servers():
  try:
      with open('server_running.json', 'r') as file:
          return json.load(file)
  except FileNotFoundError:
      return {}


def format_number(number):
  if number >= 1000000:
      return f"{number / 1000000:.1f}M"
  elif number >= 1000:
      return f"{number / 1000:.1f}K"
  else:
      return str(number)

def is_user_subscribed(user_id):
  try:
      with open("sub_users.json", "r") as file:
          subscribed_users = json.load(file)
  except FileNotFoundError:
      subscribed_users = []
  return user_id in subscribed_users


def save_log(user_id, server_name, rps):
  log_file = f"{user_id}_logs.json"
  log_entry = {
      'datetime': datetime.now().isoformat(),
      'server': server_name,
      'rps': rps
  }
  try:
      with open(log_file, 'r+') as file:
          logs = json.load(file)
          logs.append(log_entry)
          file.seek(0)
          json.dump(logs, file, indent=4)
  except FileNotFoundError:
      with open(log_file, 'w') as file:
          json.dump([log_entry], file, indent=4)

async def send_log_to_user(context, chat_id, user_id, server_name, user_name):
  log_file = f"{user_id}_logs.json"
  language = load_user_language(user_id)
  try:
      with open(log_file, 'r') as file:
          logs = json.load(file)
          log_messages = [f"Requests ghi nhận của {server_name}"] if language == "vi" else [f"Attack Logs on {server_name}"]
          for log in logs:
              log_messages.append(f"{log['datetime']} | Rps: {log['rps']}")
          log_message_text = "\n".join(log_messages) + f"\nBy @{user_name}"

          await context.bot.send_message(chat_id=chat_id, 
                                         text=f"```\n{log_message_text}\n```", 
                                         parse_mode='MarkdownV2')
  except FileNotFoundError:
      await context.bot.send_message(chat_id=chat_id, 
                                     text="Không tìm thấy bản ghi nào" if language == "vi" else "No attack logs found")

def save_user_language(user_id, language):
  try:
      with open('user_languages.json', 'r+') as file:
          data = json.load(file)
  except FileNotFoundError:
      data = {}
  except json.JSONDecodeError:
      data = {}

  data[str(user_id)] = language

  with open('user_languages.json', 'w') as file:
      json.dump(data, file, indent=4)

def load_user_language(user_id):
  try:
      with open('user_languages.json', 'r') as file:
          data = json.load(file)
          return data.get(str(user_id), "en")  
  except (FileNotFoundError, json.JSONDecodeError):
      return "en"  

async def lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  language = load_user_language(update.effective_user.id)
  chat_id = update.effective_chat.id


  keyboard = [
      [InlineKeyboardButton("English 🇺🇸", callback_data='lang_en')],
      [InlineKeyboardButton("Tiếng Việt 🇻🇳", callback_data='lang_vi')]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)
  await update.message.reply_text('⚙️ Choose your language / Chọn ngôn ngữ của bạn:', reply_markup=reply_markup)

async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, server_info):
  chat_id = update.effective_chat.id
  user_name = update.callback_query.from_user.username
  language = load_user_language(update.effective_user.id)
  user_id = update.effective_user.id

  
  await asyncio.sleep(1)
  for _ in range(14):
      await update_user_data(update, context, server_info['url'])
      await asyncio.sleep(1)
  await summary_and_cleanup(update, context, server_info['name'])
  remove_running_server(user_id)

async def handle_stats_l4(update: Update, context: ContextTypes.DEFAULT_TYPE, server_info):
  chat_id = update.effective_chat.id
  user_name = update.callback_query.from_user.username
  language = load_user_language(update.effective_user.id)
  user_id = update.effective_user.id

  
  await asyncio.sleep(1)
  for _ in range(20):
      await fetch_netdata(update, user_id, server_info['url'])
      await asyncio.sleep(1)
  await summary_and_cleanup_l4(update, context, server_info['name'])
  remove_running_server(user_id)


async def top_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    language = load_user_language(update.effective_user.id)
    message_text = "Choose the type of Dstat to view 📊"
    buttons = [
        
        [InlineKeyboardButton("Layer7", callback_data="layer7_dstat_top")],
        
        
    ]
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

        




async def show_top_for_server(update: Update, context: ContextTypes.DEFAULT_TYPE, server_name: str) -> None:
    with open('user_performance.json', 'r') as file:
        data = json.load(file)

    filtered_data = []
    for username, user_data in data.items():
        if server_name in user_data:
            server_data = user_data[server_name]
            filtered_data.append((username, server_data['max'], server_data['total']))

    sorted_users = sorted(filtered_data, key=lambda x: (x[1] + x[2]) / 2, reverse=True)[:10]

    buttons = [[InlineKeyboardButton("<< Back", callback_data="layer7_dstat_top")]]

    for username, max_req, total_req in sorted_users:
        if '[¥]' in username:
            user_name, full_name = username.split('[¥]')
        else:
            user_name = username
            full_name = "None"

        if len(full_name) > 7:
            full_name = full_name[:7] + "…"
        username_link = f"https://t.me/{user_name}"
        button_text = f"{full_name}|Max:{format_number(max_req)}|All:{format_number(total_req)}"
        buttons.append([InlineKeyboardButton(button_text, url=username_link)])

    reply_markup = InlineKeyboardMarkup(buttons)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message_text = (f"🟣 🏝️ <b>{server_name}</b> Ranking 🏝️️️\n"
                    f"    ⤷ <code>Ranking Type: Overall Ranking</code>\n"
                    f"    ⤷ <code>Date: {now}</code>")

    await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')

async def show_top_for_server_l4(update: Update, context: ContextTypes.DEFAULT_TYPE, server_name: str) -> None:

  with open('user_performance_l4.json', 'r') as file:
      data = json.load(file)

  filtered_data = []
  for username, user_data in data.items():
      if server_name in user_data:
          server_data = user_data[server_name]
          filtered_data.append((username, server_data['max'], server_data['total']))

  sorted_users = sorted(filtered_data, key=lambda x: (x[1] + x[2]) / 2, reverse=True)[:10]

  buttons = [[InlineKeyboardButton("<< Back", callback_data="back_to_top_users_l4")]]

  for username, max_req, total_req in sorted_users:
      user_name, full_name = username.split('[¥]')
      if len(full_name) > 4:
          full_name = full_name[:4] + "…"
      username_link = f"https://t.me/{user_name}"
      button_text = f"{full_name}|Max:{format_data_rate(max_req)}|All:{format_data_rate(total_req)}"
      buttons.append([InlineKeyboardButton(button_text, url=username_link)])

  reply_markup = InlineKeyboardMarkup(buttons)
  now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  message_text = (f"🟣 🏝️ <b>{server_name}</b> Ranking 🏝️️️\n"
                  f"    ⤷ <code>Ranking Type: Overall Ranking</code>\n"
                  f"    ⤷ <code>Date: {now}</code>")

  await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='HTML')


async def show_top_servers_l4(update: Update, context: ContextTypes.DEFAULT_TYPE, servers, layer_type):
    language = load_user_language(update.effective_user.id)
    message_text = "Choose Server to view 📊"
    buttons = [
        [InlineKeyboardButton(f"👑 {server['name']} 👑", callback_data=f"l4top_{server['name']}")]
        for server in servers
    ]
    buttons.append([InlineKeyboardButton("<< Back", callback_data="back_to_dstat_type")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)


async def show_top_servers_l7(update: Update, context: ContextTypes.DEFAULT_TYPE, servers, layer_type):
    language = load_user_language(update.effective_user.id)
    message_text = "Choose Server to view 📊"
    buttons = [
        [InlineKeyboardButton(f"👑 {server['name']} 👑", callback_data=f"l7top_{server['name']}")]
        for server in servers
    ]
    buttons.append([InlineKeyboardButton("<< Back", callback_data="back_to_dstat_type")])
    reply_markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)

    

def save_user_performance(user_name, full_name, max_requests, total_requests, server_name):
  try:
      with open('user_performance.json', 'r+') as file:
          data = json.load(file)
          user_key = f"{user_name}[¥]{full_name}"  

          if user_key not in data:
              data[user_key] = {}

          if server_name not in data[user_key]:
              data[user_key][server_name] = {'max': max_requests, 'total': total_requests}
          else:
              old_avg = (data[user_key][server_name]['max'] + data[user_key][server_name]['total']) / 2
              new_avg = (max_requests + total_requests) / 2

              if new_avg > old_avg:
                  data[user_key][server_name]['max'] = max_requests
                  data[user_key][server_name]['total'] = total_requests

          file.seek(0)
          json.dump(data, file, indent=4)
          file.truncate()
  except FileNotFoundError:
      with open('user_performance.json', 'w') as file:
          json.dump({user_key: {server_name: {'max': max_requests, 'total': total_requests}}}, file, indent=4)

def save_user_performance_l4(user_name, full_name, max_received, total_received, server_name):
  try:
      with open('user_performance_l4.json', 'r+') as file:
          data = json.load(file)
          user_key = f"{user_name}[¥]{full_name}"  

          if user_key not in data:
              data[user_key] = {}

          if server_name not in data[user_key]:
              data[user_key][server_name] = {'max': max_received, 'total': total_received}
          else:
              old_avg = (data[user_key][server_name]['max'] + data[user_key][server_name]['total']) / 2
              new_avg = (max_received + total_received) / 2

              if new_avg > old_avg:
                  data[user_key][server_name]['max'] = max_received
                  data[user_key][server_name]['total'] = total_received

          file.seek(0)
          json.dump(data, file, indent=4)
          file.truncate()
  except FileNotFoundError:
      with open('user_performance_l4.json', 'w') as file:
          json.dump({user_key: {server_name: {'max': max_received, 'total': total_received}}}, file, indent=4)

async def add_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  args = context.args
  if update.effective_user.id not in admin_ids:
      return

  if len(args) != 3:
      await update.message.reply_text("Usage: /add <tên> <url nginx_status> <loại bảo vệ>")
      return

  new_server = {
      "name": args[0],
      "url": args[1],
      "protection_type": args[2]
  }

  try:
      with open('servers.json', 'r+') as file:
          data = json.load(file)
          data["servers"].append(new_server)
          file.seek(0)
          json.dump(data, file, indent=4)
          file.truncate()
  except FileNotFoundError:
      with open('servers.json', 'w') as file:
          json.dump({"servers": [new_server]}, file, indent=4)

  await update.message.reply_text(f"Server {args[0]} được thêm thành công!")

async def add_server_l4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  args = context.args
  if update.effective_user.id not in admin_ids:
      return

  if len(args) != 4:
      await update.message.reply_text("Usage: /add [tên] [url data] [ip] [loại bảo vệ]")
      return

  new_server = {
      "name": args[0],
      "url": args[1],
      "ip" : args[2],
      "protection_type": args[3]
  }

  try:
      with open('l4_servers.json', 'r+') as file:
          data = json.load(file)
          data["servers"].append(new_server)
          file.seek(0)
          json.dump(data, file, indent=4)
          file.truncate()
  except FileNotFoundError:
      with open('servers.json', 'w') as file:
          json.dump({"servers": [new_server]}, file, indent=4)

  await update.message.reply_text(f"Server {args[0]} được thêm thành công!")


async def remove_server(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  args = context.args
  if update.effective_user.id not in admin_ids:
      return

  if len(args) != 1:
      await update.message.reply_text("Usage: /rm <tên server>")
      return

  server_name = args[0]
  servers = load_servers()
  updated_servers = [server for server in servers if server['name'] != server_name]

  if len(updated_servers) < len(servers):
      with open('servers.json', 'w') as file:
          json.dump({'servers': updated_servers}, file, indent=4)
      await update.message.reply_text(f"Server {server_name} đã được xoá thành công!")
  else:
      await update.message.reply_text(f"Không tìm thấy server có tên {server_name} để xoá.")

async def remove_server_l4(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  args = context.args
  if update.effective_user.id not in admin_ids:
      return

  if len(args) != 1:
      await update.message.reply_text("Usage: /rm [tên server]")
      return

  server_name = args[0]
  servers = load_l4servers()
  updated_servers = [server for server in servers if server['name'] != server_name]

  if len(updated_servers) < len(servers):
      with open('l4_servers.json', 'w') as file:
          json.dump({'servers': updated_servers}, file, indent=4)
      await update.message.reply_text(f"Server {server_name} đã được xoá thành công!")
  else:
      await update.message.reply_text(f"Không tìm thấy server có tên {server_name} để xoá.")

async def list_servers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  servers = load_servers()

  if update.effective_user.id not in admin_ids:
      return

  language = load_user_language(update.effective_user.id)
  if servers:
      message_text = "Danh sách Server:\n\n" if language == "vi" else "List Server:\n\n"
      for server in servers:
          message_text += f"[+] Tên: <b>{server['name']}</b>\n  URL: <code>{server['url']}</code>\n  Loại Bảo Vệ: <b>{server['protection_type']}</b>\n\n" if language == "vi" else f"[+] Name: <b>{server['name']}</b>\n  URL: <code>{server['url']}</code>\n  Protection Type: <b>{server['protection_type']}</b>\n\n"
  else:
      message_text = "Chưa có server nào được thêm" if language == "vi" else "No servers has been added"

  await update.message.reply_text(message_text, parse_mode='HTML')

def load_servers():
  try:
      with open('servers.json', 'r') as file:
          data = json.load(file)
          return data.get('servers', [])
  except FileNotFoundError:
      return []

def load_l4servers():
  try:
      with open('l4_servers.json', 'r') as file:
          data = json.load(file)
          return data.get('servers', [])
  except FileNotFoundError:
      return []

def save_servers(servers):
  with open('servers.json', 'w') as f:
      json.dump(servers, f, indent=4)

async def fetch_nginx_status(update, server_url):
  async with httpx.AsyncClient() as client:
      response = await client.get(server_url)
      language = load_user_language(update.callback_query.from_user.id)
      if response.status_code == 200:
          return int(response.text.split(" ")[9].strip())
      else:
          return "Error while connect to Server" if language == "en" else "Lỗi khi kết nối đến Server"


async def fetch_netdata(update, user_id, target):
    api_url = target
    async with httpx.AsyncClient(timeout=6.0) as client:
        try:
            response = await client.get(api_url)
            language = load_user_language(update.callback_query.from_user.id)
            if response.status_code == 200:
                data = response.json()
                value = round(data['latest_values'][0], 1) if 'latest_values' in data and len(data['latest_values']) >= 0 else -1
            else:
                value = -1
        except Exception as e:
            value = -1
            print(f"Error while connecting to API: {str(e)}")  
        save_netdata(user_id, "net_received", {"value": int(value)})


def save_netdata(user_id, key, new_entry):
    try:
        with open(f"{user_id}_data_l4.json", 'r+') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                data = {}
            if key not in data:
                data[key] = []
            data[key].append(new_entry)
            file.seek(0)
            json.dump(data, file, indent=4)
            file.truncate()
    except FileNotFoundError:
        with open(f"{user_id}_data_l4.json", 'w') as file:
            json.dump({key: [new_entry]}, file, indent=4)

def save_data(user_id, key, value):
  try:
      with open(f"{user_id}_data.json", 'r+') as file:
          try:
              data = json.load(file)
          except json.JSONDecodeError:
              data = {}
          data[key] = value
          file.seek(0)
          json.dump(data, file, indent=4)
          file.truncate()
  except FileNotFoundError:
      with open(f"{user_id}_data.json", 'w') as file:
          json.dump({key: value}, file, indent=4)

def load_data(user_id, key):
  try:
      with open(f"{user_id}_data.json", 'r') as file:
          data = json.load(file)
          return data.get(key)
  except (FileNotFoundError, json.JSONDecodeError):
      return None

async def update_user_data(update, context, server_url):
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id
    previous_value = load_data(user_id, 'previous_value')
    differences = load_data(user_id, 'differences') or []
    message_ids = load_data(user_id, 'message_ids') or []
    difference = 0
    total_difference = 0

    try:
        new_value = await fetch_nginx_status(update, server_url)
        if new_value is not None and previous_value is not None:
            difference = new_value - previous_value
            differences.append(difference)
            total_difference = sum(differences)

            message_text = f"```\nRequests Per Second: {difference:,}\nTotal Requests: {total_difference:,}\n```"
 
            message = await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode='MarkdownV2')
            message_ids.append(message.message_id)

            await asyncio.sleep(5)
            await context.bot.delete_message(chat_id=chat_id, message_id=message.message_id)

        previous_value = new_value

        save_log(user_id, server_url, difference)
        save_data(user_id, 'previous_value', new_value if new_value is not None else 0)
        save_data(user_id, 'differences', differences)
        save_data(user_id, 'message_ids', message_ids)

    except Exception as e:
        print(f"Error in update_user_data: {e}")
        difference = 0
        differences.append(difference)
        save_data(user_id, 'differences', differences)
        save_log(user_id, server_url, difference)
        save_data(user_id, 'message_ids', message_ids)

async def summary_and_cleanup(update, context, server_name):
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id
    
    differences = load_data(user_id, 'differences') or []
    message_ids = load_data(user_id, 'message_ids') or []
    now = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

    async def check_and_remove_server(user_id, server_name):
        await asyncio.sleep(1)
        remove_running_server(user_id)
    asyncio.create_task(check_and_remove_server(user_id, server_name))

    try:
        if differences:
            max_difference = max(differences)
            total_difference = sum(differences)
            average_difference = round(total_difference / len(differences), 2)

            if update.callback_query.message and update.callback_query.from_user:
                user_mention = f"[{update.callback_query.from_user.first_name}](tg://user?id={update.callback_query.from_user.id})"

                summary_message = (
                    f"🛡{server_name}🛡\n"
                    f"Statistics end\n"
                    "✅ The statistics are as follows ✅\n"
                    f"Peak visits per second: {max_difference:,}\n"
                    f"Average visits: {round(average_difference):,}\n"
                    f"Total visits: {total_difference:,}\n"
                    f"Today: {now}\n"
                    
                )

                full_name = update.callback_query.from_user.full_name
                user_name = update.callback_query.from_user.username
                save_user_performance(user_name, full_name, max_difference, total_difference, server_name)
                
                await context.bot.send_message(chat_id=chat_id, text=f"```{summary_message}```\n\n🚗 Data from user: {user_mention} 🚗", parse_mode='MarkdownV2')

            else:
                await context.bot.send_message(chat_id=chat_id, text="User data is not available", parse_mode='MarkdownV2')
        else:
            await context.bot.send_message(chat_id=chat_id, text="No data to display", parse_mode='MarkdownV2')

        for msg_id in message_ids:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                print(f"Error deleting message {msg_id}: {e}")

        remove_running_server(user_id)
        os.remove(f"{user_id}_data.json")
        os.remove(f"{user_id}_logs.json")
    
    except Exception as e:
        print(f"Error in summary_and_cleanup: {e}")

def create_summary_message(language, server_name, total_received, max_received, average_received, update):
    total_received_formatted = format_data_rate(total_received)
    max_received_formatted = format_data_rate(max_received)
    average_received_formatted = format_data_rate(average_received)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if language == 'vi':
        return (
            f"Dstat Layer 4 <b>{server_name}</b> đã kết thúc\n<b>{now}</b>\n\n"
            f"Kết quả ghi nhận trong 120 giây:\n"
            f"[>] Tổng lượng dữ liệu: <b>{total_received_formatted}</b>\n"
            f"[>] Lượng dữ liệu cao nhất: <b>{max_received_formatted}</b>\n"
            f"[>] Trung Bình Lượng dữ liệu: <b>{average_received_formatted}</b>\n\n"
            "Cảm ơn bạn vì đã sử dụng <b>DstatCountBot</b> ❤️\n"
            f"@{update.callback_query.from_user.username}"
        )
    else:
        return (
            f"Dstat Layer 4 <b>{server_name}</b> has been ended\n<b>{now}</b>\n\n"
            f"Stats during 120 seconds:\n"
            f"[>] Total Data Rate: <b>{total_received_formatted}</b>\n"
            f"[>] Peak Data Rate: <b>{max_received_formatted}</b>\n"
            f"[>] Average Data Rate: <b>{average_received_formatted}</b>\n\n"
            "Thanks for using <b>DSTATCOUNT</b> ❤️\n"
            f"@{update.callback_query.from_user.username}"
        )


async def summary_and_cleanup_l4(update, context, server_name):
    user_id = update.callback_query.from_user.id
    chat_id = update.callback_query.message.chat_id
    language = load_user_language(update.effective_user.id)

    try:
        with open(f"{user_id}_data_l4.json", 'r') as file:
            data = json.load(file)
            net_received = [entry['value'] for entry in data['net_received'] ]
    except (FileNotFoundError, KeyError):
        net_received = []

    if net_received:
        max_received = max(net_received)
        total_received = sum(net_received)
        average_received = round(total_received / len(net_received), 2) if net_received else 0

        summary_message = create_summary_message(language, server_name, total_received, max_received, average_received, update)

        full_name = update.callback_query.from_user.full_name
        user_name = update.callback_query.from_user.username
        save_user_performance_l4(user_name, full_name, max_received, total_received, server_name)

        await send_graphl4_to_user(update, context, chat_id, user_id, server_name, summary_message)
    else:
        await context.bot.send_message(chat_id=chat_id, 
                                       text="Không có dữ liệu để hiển thị" if language == "vi" else "No data to display", 
                                       parse_mode='HTML')

    # Clean up files
    os.remove(f"{user_id}_data_l4.json")
    os.remove(f"{user_id}_graph_l4.png")
    

    
async def count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  language = load_user_language(update.effective_user.id)
  chat_id = update.effective_chat.id
  user_id = update.effective_user.id



  keyboard = [
      [InlineKeyboardButton("Layer 7 Dstat", callback_data="layer7_dstat")],
      [InlineKeyboardButton("Ranking", callback_data="layer7_dstat_top")]
  ]
  reply_markup = InlineKeyboardMarkup(keyboard)

  message_text = "Choose Dstat Type 📊"

  if update.callback_query:
      await update.callback_query.message.edit_text(message_text, reply_markup=reply_markup)
  else:
      await update.message.reply_text(message_text, reply_markup=reply_markup)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
  query = update.callback_query
  await query.answer()
  data = query.data
  user_id = update.effective_user.id
  language = load_user_language(user_id)
  if data.startswith("layer7count_"):
      server_name = data.split("layer7count_")[1]
  elif data.startswith("layer4count_"):
      server_name = data.split("layer4count_")[1]
  else:
          server_name = data

  if data == "layer7_dstat":
    servers = load_servers()  #
    await show_servers(update, context, servers, "layer7")
    return

  if data == "layer4_dstat":
    servers = load_l4servers()  
    await show_servers(update, context, servers, "layer4")
    return

  if data == "layer7_dstat_top":
    servers = load_servers() 
    await show_top_servers_l7(update, context, servers, "layer7")
    return

  if data == "layer4_dstat_top":
    servers = load_l4servers()  # This should load Layer 4 servers
    await show_top_servers_l4(update, context, servers, "layer4")
    return

  if data.startswith("l7top_"):
    server_name = data.split("_")[1]
    await show_top_for_server(update, context, server_name)
    return

  if data.startswith("l4top_"):
    server_name = data.split("_")[1]
    await show_top_for_server_l4(update, context, server_name)
    return

  if data.startswith('lang_'):
    language = data.split('_')[1]
    save_user_language(query.from_user.id, language)
    await query.edit_message_text(text=f"Language set to {'English 🇺🇸' if language == 'en' else 'Tiếng Việt 🇻🇳'}")
    add_user_to_subscribed(user_id)
    return

  if data == "back_to_dstat_type":
    await top_users(update, context)
    return

  if data == "back_to_top_users":
    servers = load_servers() 
    await show_top_servers_l7(update, context, servers, "layer7")
    return

  if data == "back_to_top_users_l4":
    servers = load_l4servers() 
    await show_top_servers_l4(update, context, servers, "layer4")
    return

  if data == "back_to_dstatcount_type":
    await count(update, context)
    return


  current_server = load_running_server(user_id)
  if (current_server and current_server != server_name) or (current_server and current_server == server_name):
      await query.edit_message_text(text="Bạn đang sử dụng một server. Vui lòng hoàn thành trước khi sử dụng server khác." if language == "vi" else "You are already using a server. Please complete that before using another one.")
      return
  if server_name in load_all_running_servers().values() and current_server != server_name:
      await query.edit_message_text(text="Server này đang được người khác sử dụng. Vui lòng chọn server khác." if language == "vi" else "This server is currently in use by another user. Please select a different server.")
      return


  if data.startswith('layer7count_'):
    servers = load_servers()
    server_info = next((server for server in servers if server['name'] == server_name), None)
    if server_info is None:
        return
    chat_id = update.effective_chat.id
    parsed_url = urlparse(server_info['url'])
    simplified_url = f"{parsed_url.scheme}://{parsed_url.netloc}/"

    message_text = (f"🏝️<b>{server_info['name']}</b> 🏝️\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
                "Dstat Start\n"
                f"Target (Click to copy URL): <code>{simplified_url}</code>\n"
                f"Protection Type: <b>{server_info['protection_type']}</b>\n"
                "Statistics Duration: <b>120 Second</b>")

    if server_info:
      save_running_server(user_id, server_name)
      await context.bot.send_message(chat_id=chat_id, text=message_text, parse_mode='HTML')
      asyncio.create_task(handle_stats(update, context, server_info))
    else:
      await query.edit_message_text(text="Không tìm thấy thông tin Server" if language == "vi" else "Server infomation not found", parse_mode='HTML')

  if data.startswith('layer4count_'):
      servers = load_l4servers()
      server_info = next((server for server in servers if server['name'] == server_name), None)
      if server_info is None:
          return
      target = server_info['ip']

      message_text = (f"Server: 🏝️<b>{server_info['name']}</b> 🏝️\n"
                      "- Bắt đầu ghi dữ liệu\n"
                      f"- Mục Tiêu (Ấn vào để copy URL): <code>{target}</code> | Port: 22\n"
                      f"- Loại Bảo Vệ: <b>{server_info['protection_type']}</b>\n"
                      "- Ghi dữ liệu trong: <b>120s</b>") if language == "vi" else (f"Server Name: 🏝️<b>{server_info['name']}</b> 🏝️\n"
                      "- Statistics have started\n"
                      f"- Target (Click to copy URL): <code>{target}</code> | Port: 22\n"
                      f"- Protection Type: <b>{server_info['protection_type']}</b>\n"
                      "- Statistics Duration: <b>120s</b>")

      if server_info:
        save_running_server(user_id, server_name)
        await query.edit_message_text(text=message_text, parse_mode='HTML')
        asyncio.create_task(handle_stats_l4(update, context, server_info))
      else:
        await query.edit_message_text(text="Không tìm thấy thông tin Server" if language == "vi" else "Server infomation not found", parse_mode='HTML')

async def clr(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

  if update.effective_user.id in admin_ids:
      with open('server_running.json', 'w') as file:
          file.write('{}')
      await update.message.reply_text("Clear")
  else:
      return

async def delete_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args

    if update.effective_user.id not in admin_ids:
        return

    if len(args) != 2:
        await update.message.reply_text('Usage: /del [username] [server]')
        return

    username, server_to_delete = args
    modified = False

    try:
        with open('user_performance.json', 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        await update.message.reply_text('Error reading performance data.')
        return

    for user_key, servers in data.items():
        if user_key.startswith(username + "-"):
            if server_to_delete in servers:
                del servers[server_to_delete]
                modified = True
                break

    if modified:
        with open('user_performance.json', 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        await update.message.reply_text(f'Xoá thành công top Server {server_to_delete} của {username}')
    else:
        await update.message.reply_text(f'Người dùng {username} không nằm trong top Server {server_to_delete}')

async def reset_rank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

  if update.effective_user.id in admin_ids:
      with open('user_performance.json', 'w') as file:
          file.write('{}')
      with open('user_performance_l4.json', 'w') as file:
          file.write('{}')
      await update.message.reply_text("Clear Ranking")
  else:
      return


app = ApplicationBuilder().token("6777690636:AAEjDNkc95N2pd-LFfQsp9h1I1oqIsC2-y0").build()

app.add_handler(CommandHandler("dstat", count))
app.add_handler(CommandHandler("add", add_server))

app.add_handler(CommandHandler("rm", remove_server))

app.add_handler(CommandHandler("sv", list_servers))
app.add_handler(CommandHandler("top", top_users))
app.add_handler(CallbackQueryHandler(button_callback))

app.add_handler(CommandHandler("clr", clr))
app.add_handler(CommandHandler("del", delete_ranking))
app.add_handler(CommandHandler("reset", reset_rank))

print("done")
app.run_polling()
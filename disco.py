from discord_webhook import DiscordWebhook, DiscordEmbed
import configparser

# Config parser for API connection info
config = configparser.ConfigParser()
config.read("secret.ini")

disco_url = config['discord']['webhook_url']
disco_hook = DiscordWebhook(url=disco_url)

def disco_log(title: str, message: str) -> None:
    """ Log a message to Discord via webhook """
    embed = DiscordEmbed(title=title, description=message, color='03b2f8')
    disco_hook.add_embed(embed)
    response = disco_hook.execute()
    disco_hook.remove_embeds()
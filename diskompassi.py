from discord.ext import tasks
import json
import discord
import requests

def get_config() -> dict:
    f = open("diskompassi.json","r")
    j = json.load(f)
    f.close()
    return j

class Diskompassi(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = get_config()
    
    async def setup_hook(self) -> None:
        self.import_kompassi_roles.start()

    def save_config(self) -> None:
        f = open("diskompassi.json","w")
        json.dump(self.config, f, indent=2)
        f.close()
        print("Saved config")

    async def on_ready(self) -> None:
        print(f'Logged on as {self.user}!')

    async def list_mappings(self, message) -> None:
        rolemaps_for_this_server = []
        for role in self.config['rolemaps'].keys():
            for guildmap in self.config['rolemaps'][role]:
                if(guildmap['guild'] == message.guild.id):
                    role_name = "N/A"
                    try:
                        role_name = message.guild.get_role(guildmap['role']).name
                    except:
                        pass
                    rolemaps_for_this_server.append({'kompassi_role': role, 'guild_role': role_name})
      
        if(len(rolemaps_for_this_server) == 0):
            await message.channel.send("This server has no Kompassi role maps")
            return
        reply = "Role maps in this server:\n"
        for r in rolemaps_for_this_server:
            reply = reply+"* {} -> {}\n".format(r['kompassi_role'], r['guild_role'])
        reply = reply[:-1] # Remove last \n
        await message.channel.send(reply)

    async def add_mapping(self, message) -> None:
        msg_args = message.content.split(" ")
        kompassi_role = msg_args[2]
        event = kompassi_role.split("/")[0]
        if(event not in self.config['events']):
            self.config['events'].append(event)
        guild_role = msg_args[3]
        if(guild_role.startswith("<@&")):
            guild_role = guild_role[3:-1]
        guild_role = int(guild_role)
        print(guild_role)
        guild_role_name = message.guild.get_role(guild_role).name
        if(kompassi_role not in self.config['rolemaps']):
            self.config['rolemaps'][kompassi_role] = []
        self.config['rolemaps'][kompassi_role].append({'guild': message.guild.id, 'role': guild_role})
        self.save_config()
        await message.channel.send("Mapping added: {} -> {}".format(kompassi_role, guild_role_name))

    async def delete_mapping(self, message) -> None:
        msg_args = message.content.split(" ")
        kompassi_role = msg_args[2]
        if(kompassi_role not in self.config['rolemaps']):
            message.channel.send("Kompassi rule not found")
            return
        for guildmap in self.config['rolemaps'][kompassi_role]:
            if(guildmap['guild'] == message.guild.id):
                self.config['rolemaps'][kompassi_role].remove(guildmap) # Assume one-to-one mapping
        self.save_config()

    async def on_message(self, message):
        if(message.content.startswith("%kompassi")):
            msg_args = message.content.split(" ")
            if(len(msg_args) == 1):
                return
            for allowed_role in self.config['admin_roles']:
                if(message.author.get_role(allowed_role)):
                    if(msg_args[1] == "list_mappings"):
                        await self.list_mappings(message)
                    elif(msg_args[1] == "add_mapping"):
                        await self.add_mapping(message)
                    elif(msg_args[1] == "delete_mapping"):
                        await self.delete_mapping(message)
                    elif(msg_args[1] == "run_mapping_now"):
                        await self.import_kompassi_roles()
            if(message.author.id in self.config["superadmin"]):
                if(msg_args[1] == "add_admin_role"):
                    self.config['admin_roles'].append(int(msg_args[2]))
                    self.save_config()
                    message.channel.send("Admin role added")

    @tasks.loop(seconds=60*60)
    async def import_kompassi_roles(self):
        for e in self.config['events']:
            res = requests.get("https://kompassi.eu/api/v1/events/{}/discord".format(e), auth=(self.config['kompassi_user'], self.config['kompassi_pass']))
            try:
                j = res.json() # [{"handle": "japsu", "roles": ["Coniitti"]}]
            except:
                print("Failed when parsing json. Received:")
                print(res.text)
                continue
            #TESTJSON = '[{"handle": "fwe", "roles": ["Coniitti"]}]'
            #j = json.loads(TESTJSON)
            for row in j:
                for role in row['roles']:
                    roleid = "{}/{}".format(e, role)
                    if(roleid not in self.config['rolemaps']):
                        # print("Warning: No mapping for", roleid)
                        continue

                    for role_mapping in self.config['rolemaps'][roleid]:
                        guild = self.get_guild(role_mapping['guild'])
                        if(guild is None):
                            print("Error: Bot not in {}".format(role_mapping['guild']))
                            continue
                        role = guild.get_role(role_mapping['role'])
                        if(role is None):
                            print("Error: Server {} does not have role {}".format(role_mapping['guild'], role_mapping['role']))
                        # Cannot use guild.get_member_named, because the lookup order is..non-ideal.
                        for m in guild.members:
                            if(m.name == row['handle'].lower()):
                                if not m.get_role(role_mapping['role']):
                                    print("Assigning {} to {}".format(roleid, row['handle']))
                                    await m.add_roles(role, reason = "Kompassi import")
                                break

    @import_kompassi_roles.before_loop
    async def before_start(self):
        await self.wait_until_ready()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

config = get_config()
client = Diskompassi(intents=intents)
client.run(config['discord_token'])

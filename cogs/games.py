"""
Slash commands for games
"""

import discord
from discord import app_commands, SelectOption
from discord.ext import commands
from discord.ui import View, Select
import random, asyncio, json, os
from datetime import datetime, timedelta, timezone
from utils.booster_manager import check_boost_status
from utils.quote_manager import load_quotes
from utils.vote_manager import load_votes, update_tierlist_message, get_votes_from_user_data
from utils.cooldown_manager import *

class Games(commands.Cog):
    """
    A cog for various games using slash commands
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.cooldowns = {}

    async def get_msg_count_roast(self, interaction: discord.Interaction, user: discord.Member, roasts: dict) :
        total_msgs = 0
        user_msgs = 0
        print(f"Fetching up to 5000 messages in #{interaction.channel.name}...")

        time_limit = datetime.now(timezone.utc) - timedelta(days=7)

        # Fetch messages in chunks to avoid API rate limits
        async for msg in interaction.channel.history(limit=5000, after=time_limit):
            total_msgs += 1
            if msg.author.id == user.id:
                user_msgs += 1

        percent = round((user_msgs / total_msgs) * 100, 2) if total_msgs else 0

        quips = roasts["quips"]

        if percent <= 0.2:
            quip = random.choice(quips["0.2"])
        elif percent <= 0.6:
            quip = random.choice(quips["0.6"])
        elif percent <= 1.5:
            quip = random.choice(quips["1.5"])
        elif percent <= 4:
            quip = random.choice(quips["4"])
        else:
            quip = random.choice(quips[">4"])

        message = (
            f"{user.mention} has sent {user_msgs} messages in this channel in the last week. "
            f"That's about {percent}% of the messages sent last week! {quip}"
        )

        # Truncate message to 2000 characters just in case
        return message[:2000]

    async def get_display_name(self, guild: discord.Guild, user_id: int):
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        try:
            member = await guild.fetch_member(user_id)
            return member.display_name
        except discord.NotFound:
            return f"User {user_id}"
        except discord.HTTPException:
            return f"User {user_id}"
        
    # autocomplete callback for flavor choices
    async def flavor_autocomplete(self, interaction: discord.Interaction, current: str):
        flavors = load_votes(interaction.guild_id)
        return [
            app_commands.Choice(name=flavor, value=flavor)
            for flavor in list(flavors.keys()) if current.lower() in flavor.lower()
        ][:25]  # Discord max 25 choices

    @app_commands.command(name="catchadew", description="Catch the Dew can! Type '[catch]' as fast as you can!")
    async def catchadew(self, interaction: discord.Interaction):
        EMOJI_ID = "<:dewcan:653121636551098379>" 
        jump_count = 0
        # user checker
        is_valid_user = await check_boost_status(self.bot, interaction) 
        if(not is_valid_user):
            await interaction.response.send_message("Sorry bro, you're not cool enough to use this. Have you tried boosting? Or maybe ask a booster or mod politely?", ephemeral=True)
        else:
            # randomized catch generator
            base_catch = "[catch]"
            for letter in range(len(base_catch)):
                if(random.randint(0, 1) == 0) and ((base_catch[letter] != "[" or base_catch[letter] !=']')): # if num is 0, make it uppercase
                    base_catch = base_catch.replace(base_catch[letter], base_catch[letter].upper())

            await interaction.response.send_message(f"Catch a Dew can! First person to type '{base_catch}' wins!")
            await asyncio.sleep(1)
            followup = await interaction.followup.send(f"Get ready to catch the can! Type '{base_catch}' as fast as you can!", wait=True)
            base_msg = followup.content
            in_between = random.uniform(0.45, 1.25)  # random time between jumps

            # actual logic for can
            while jump_count < 4:
                if(jump_count == 3):
                    await followup.edit(content=f"{base_msg}" + "\n" * (jump_count + 1) + f"{EMOJI_ID}\nCatch it now! Type '{base_catch}'!")
                    break
                await followup.edit(content=f"{base_msg}" + "\n" * (jump_count + 1) + f"{EMOJI_ID}")
                await asyncio.sleep(in_between)
                jump_count += 1
            
            def check(m):
                return m.content == base_catch and m.channel.id == interaction.channel_id

            try:
                msg = await self.bot.wait_for("message", timeout=0.65, check=check)
                await interaction.followup.send(f"I'm not Tartt but {msg.author.mention} caught the Dew can! Congratulations!")
            except asyncio.TimeoutError:
                await interaction.followup.send("I am gonna get fired probably")
            except discord.Forbidden:
                print("Unable to send message. Missing permissions?")

    @app_commands.command(name="roast", description="Roast yourself (or a user if you're cool) with a random roast!")
    async def roast(self, interaction: discord.Interaction, user:  discord.Member = None):
        if user is None:
            user = interaction.user

        # defer the response for long-running operations
        await interaction.response.defer(ephemeral=False)

        # load roast data
        with open("data/roasts.json", "r") as f:
            roast_dict = json.load(f)
        roasts = roast_dict["roasts"]

        # decide if we do the message-count-based roast (~7.5% chance)
        if random.random() < 0.075:
            message = await self.get_msg_count_roast(interaction, user, roast_dict)
        else:
            # Random generic roast
            random_roast_num = random.randint(0, len(roasts) - 1)
            message = f"{user.mention} {roasts[random_roast_num]}"

        # Send the followup after defer
        await interaction.followup.send(message[:2000])

        # Apply cooldown if necessary
        if not await check_boost_status(self.bot, interaction):
            await set_cooldown(interaction)

    @app_commands.command(name="recall", description="Pull a random memory (or any user's if you're cool)")
    async def recall(self, interaction: discord.Interaction, user: discord.Member = None, ping: bool = False):
        # check if user is allowed to use this command (booster check)
        COOLDOWN_TIME = 600 # 10 minutes
        is_valid_user = await check_boost_status(self.bot, interaction)
        if(not is_valid_user):
            if await check_cooldown(interaction, COOLDOWN_TIME):
                time_left = await get_remaining_cooldown(interaction, COOLDOWN_TIME)
                await interaction.response.send_message(f"You're on cooldown! Try again in {time_left}.", ephemeral=True)
        quote = {}
        data = await load_quotes()  # load all saved quotes
        if not data:
            # no quotes found, tell user how to save one
            await interaction.response.send_message("No quotes available. Try saving some by selecting a message, going to Apps, and then 'Save Quote!'")
            return
        randomized = False
        recall_data = data[str(interaction.guild_id)][str(interaction.user.id)]["recalls"]
        # if user isn't valid or didn't specify a user, just pick a random quote from their own recalls
        if(not is_valid_user or user is None):
            quote = random.choice(recall_data)
            randomized = True
        if(randomized == False):
            # user is valid and specified a user, so let them pick from a list of that user's quotes
            print("Selected quote...")
            filtered_recall = [q for q in recall_data if str(q.get("msg_author_id")) == str(user.id)]
            options = []
            for q in filtered_recall[:25]:  # discord only allows 25 options in a select
                author = interaction.guild.get_member(int(q["msg_author_id"]))
                author_name = author.display_name if author else "Unknown"
                label = f'{author_name}: {q["content"][:50]}'  # show author and first 50 chars of quote
                options.append(SelectOption(label=label, value=q["message_id"]))

            # create select menu for user to pick a quote
            select = Select(placeholder="Pick a quote...", options=options, min_values=1, max_values=1)

            # callback for when user picks a quote
            async def select_callback(select_interaction: discord.Interaction):
                selected_id = select.values[0]
                selected_quote = next(q for q in filtered_recall if q["message_id"] == str(selected_id))
                author_id = selected_quote["msg_author_id"]
                author = await self.get_display_name(interaction.guild, author_id)
                response = f'"{selected_quote["content"]}" — {author}'
                if ping:
                    response = f'"{selected_quote["content"]}" — <@{author_id}>'
                await select_interaction.response.send_message(response)

            select.callback = select_callback  # set the callback for the select menu
            view = View()
            view.add_item(select)  # add select to the view
            await interaction.response.send_message("Choose a quote:", view=view, ephemeral=True)
        else:
            # just send a random quote (either not a booster or no user specified)
            print("Randomized quote...")
            author_id = quote["msg_author_id"]
            author = await self.get_display_name(interaction.guild, author_id)
            print(author)
            if ping:
                await interaction.response.send_message(f'"{quote["content"]}" — <@{author_id}>')
                if not is_valid_user:
                    await set_cooldown(interaction)
                    return
            await interaction.response.send_message(f'"{quote["content"]}" — {author}')
            if not is_valid_user:
                await set_cooldown(interaction)  

    @app_commands.command(name="vote", description="Once a day, vote for a flavor on the tierlist!")
    async def vote(self, interaction: discord.Interaction, flavor: str, score: app_commands.Range[int, 1, 10]):
        # add cooldown
        COOLDOWN_TIME = 86400
        if await check_cooldown(interaction, COOLDOWN_TIME):
            time_left = await get_remaining_cooldown(interaction, COOLDOWN_TIME)
            await interaction.response.send_message(f"You already voted! Try again in {time_left}.", ephemeral=True)
            return
        with open("data/server_data.json", "r+") as f:
            data = json.load(f)
            guild_id = str(interaction.guild_id)
            # save to vote item data
            prev_score = data[guild_id]["vote_items"][flavor]["total_score"]
            if(prev_score is None):
                prev_score = 0
            data[guild_id]["vote_items"][flavor]["vote_num"] += 1
            data[guild_id]["vote_items"][flavor]["total_score"] += score
            data[guild_id]["vote_items"][flavor]["score"] = (data[guild_id]["vote_items"][flavor]["total_score"] / data[guild_id]["vote_items"][flavor]["vote_num"])
            f.seek(0)
            json.dump(data, f, indent=4) # saves to file
            f.truncate()

        # saves vote data to server's user data
        with open("data/user_data.json", "r+") as f:
            data = json.load(f)
            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            # save to user data
            if guild_id not in data:
                data[guild_id] = {}
            if user_id not in data[guild_id]:
                data[guild_id][user_id] = {}
            if "votes" not in data[guild_id][user_id]:
                data[guild_id][user_id]["votes"] = {}
            if flavor not in data[guild_id][user_id]["votes"]:
                data[guild_id][user_id]["votes"][flavor] = []
            # appends score and time to vote list
            data[guild_id][user_id]["votes"][flavor].append({
                "score": score,
                "time_created": interaction.created_at.isoformat()
            })
            f.seek(0)
            json.dump(data, f, indent=4)
            f.truncate()
        await update_tierlist_message(self.bot, interaction.guild_id)
        await interaction.response.send_message(f"You voted **{score}/10** for **{flavor}**!", ephemeral=True)
        await set_cooldown(interaction)

    # Register the autocomplete method to the 'flavor' argument
    @vote.autocomplete("flavor")
    async def vote_autocomplete(self, interaction: discord.Interaction, current: str):
        print(f"Autocomplete triggered: {current}")
        return await self.flavor_autocomplete(interaction, current)
    
    @app_commands.command(name="flavorstats", description="Displays the stats for a certain flavor in the tierlist!")
    async def flavorstats(self, interaction: discord.Interaction, flavor: str):
        top_voters = []
        vote_holder = {}
        votes = await load_votes(interaction.guild_id) # gets vote_items per guild
        flavor_votes = votes[flavor]
        avg_score = flavor_votes["score"]
        vote_count = flavor_votes["vote_num"]
        # logic to determine top voters
        user_data_votes = await get_votes_from_user_data(interaction.guild_id)
        for flavor_name, votes in user_data_votes.items():  # loops through dictionary of flavors
            if flavor_name != flavor:
                continue
            for vote in votes:
                voter_id = vote["voter"]
                if voter_id not in vote_holder:
                    member = interaction.guild.get_member(int(voter_id))
                    nickname = member.display_name if member else f"User {voter_id}"
                    vote_holder[voter_id] = {
                    "total_votes": 0,
                    "nickname": nickname
                    }
                vote_holder[voter_id]["total_votes"] += 1

        # sort voters by total_votes descending and get top 3
        sorted_voters = sorted(vote_holder.items(), key=lambda x: x[1]["total_votes"], reverse=True)
        top_voters = sorted_voters[:3] #  (voter_id, {"total_votes": ..., "nickname": ...})

        output = f"**━═━═━═━┤{flavor}'s Stats├━═━═━═━**\nTop Voters:"
        for idx, voter in enumerate(top_voters, start=1):
            output += f"\n{idx}. {voter[1]['nickname']} - {voter[1]['total_votes']} votes"
        if len(top_voters) < 3: # if there are less than 3 top voters, fill in rest with None
            for idx in range(len(top_voters) + 1, 4):
                output += f"\n{idx}. None"
        output += f"\nTotal Votes: {vote_count} votes"
        output += f"\nAverage Score: {round(avg_score, 2)}"

        await interaction.response.send_message(output)

    @flavorstats.autocomplete("flavor")
    async def flavorstats_autocomplete(self, interaction: discord.Interaction, current: str):
        print(f"Autocomplete triggered for flavorstats: {current}")
        return await self.flavor_autocomplete(interaction, current)
    
    

async def setup(bot):
    await bot.add_cog(Games(bot))

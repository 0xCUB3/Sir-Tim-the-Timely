"""
Chat Commands for Sir Tim the Tim        embed = hikari.Embed(
            title="✅ Chat Channel Set",
            description="Tim will now randomly respond in this channel with snarky but helpful wisdom.",
            color=0x00FF00
        )
        
        embed.add_field(
            name="How it works",
            value=(
                "• Tim responds randomly (~25% chance)\n"
                "• Higher chance if mentioned or deadline keywords used\n"
                "• Has a 5-second cooldown to prevent spam\n"
                "• Snarky but secretly helpful and wise"
            ),
            inline=False
        )r managing Tim's chat functionality in channels.
"""

import logging
import hikari
import arc

import gemini_chat_handler

logger = logging.getLogger("sir_tim.commands.chat")

# Create a plugin for chat commands
plugin = arc.GatewayPlugin("chat")

@plugin.include
@arc.slash_command("setchat", "Set current channel for Tim to chat in (Admin only)")
async def set_chat_channel(ctx: arc.GatewayContext) -> None:
    """Set the current channel for Tim to respond in."""
    # Only allow server admins
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    # Must be used in a guild
    if not ctx.guild_id:
        await ctx.respond("This command can only be used in a server.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    try:
        llm_handler = ctx.client.get_type_dependency(gemini_chat_handler.GeminiChatHandler)
        
        # Set the current channel as the chat channel
        await llm_handler.set_chat_channel(ctx.guild_id, ctx.channel_id)
        
        embed = hikari.Embed(
            title="✅ Chat Channel Set",
            description="Tim will now randomly respond in this channel with friendly and helpful wisdom.",
            color=0x00FF00
        )
        
        embed.add_field(
            name="How it works",
            value=(
                "• Tim responds randomly (~70% chance)\n"
                "• Higher chance if mentioned or when asking questions\n"
                "• Has a short cooldown to prevent spam\n"
                "• Friendly, wise, and genuinely helpful"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Tips",
            value=(
                "• Mention Tim to get his attention\n"
                "• Ask about deadlines, stress, or MIT stuff\n"
                "• He's friendly and offers practical advice\n"
                "• Use `/removechat` to disable"
            ),
            inline=False
        )
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error setting chat channel: {e}")
        await ctx.respond("Failed to set chat channel. Please try again.", flags=hikari.MessageFlag.EPHEMERAL)

@plugin.include
@arc.slash_command("removechat", "Remove Tim's chat functionality from this server (Admin only)")
async def remove_chat_channel(ctx: arc.GatewayContext) -> None:
    """Remove Tim's chat functionality from this server."""
    # Only allow server admins
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    # Must be used in a guild
    if not ctx.guild_id:
        await ctx.respond("This command can only be used in a server.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    try:
        llm_handler = ctx.client.get_type_dependency(HuggingFaceHandler)
        
        # Remove the chat channel
        await llm_handler.remove_chat_channel(ctx.guild_id)
        
        embed = hikari.Embed(
            title="🔇 Chat Disabled",
            description="Tim will no longer respond in channels on this server.",
            color=0xFF9900
        )
        
        embed.add_field(
            name="Re-enable anytime",
            value="Use `/setchat` in any channel to re-enable Tim's chat responses.",
            inline=False
        )
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error removing chat channel: {e}")
        await ctx.respond("Failed to remove chat functionality. Please try again.", flags=hikari.MessageFlag.EPHEMERAL)

@plugin.include
@arc.slash_command("chatstatus", "Show Tim's chat status for this server (Admin only)")
async def chat_status(ctx: arc.GatewayContext) -> None:
    """Show Tim's current chat configuration."""
    # Only allow server admins
    if not ctx.member or not ctx.member.permissions.ADMINISTRATOR:
        await ctx.respond("This command can only be used by server administrators.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    # Must be used in a guild
    if not ctx.guild_id:
        await ctx.respond("This command can only be used in a server.", flags=hikari.MessageFlag.EPHEMERAL)
        return
    
    try:
        llm_handler = ctx.client.get_type_dependency(HuggingFaceHandler)
        status = llm_handler.get_status()
        
        # Check if this guild has chat enabled
        chat_channel_id = llm_handler.chat_channels.get(ctx.guild_id)
        
        embed = hikari.Embed(
            title="💬 Tim's Chat Status",
            color=0x4285F4
        )
        
        if chat_channel_id:
            embed.add_field(
                name="Status",
                value="✅ **Enabled**",
                inline=True
            )
            embed.add_field(
                name="Channel",
                value=f"<#{chat_channel_id}>",
                inline=True
            )
        else:
            embed.add_field(
                name="Status",
                value="❌ **Disabled**",
                inline=True
            )
            embed.add_field(
                name="Channel",
                value="None set",
                inline=True
            )
        
        embed.add_field(
            name="Settings",
            value=(
                f"• Model: `{status.get('model', 'tinyllama')}`\n"
                f"• Base response chance: {status['base_response_chance']*100:.0f}%\n"
                f"• Cooldown: {status['cooldown_seconds']} seconds\n"
                f"• Total active servers: {status['active_channels']}"
            ),
            inline=False
        )
        
        if not chat_channel_id:
            embed.add_field(
                name="Enable Chat",
                value="Use `/setchat` in the channel where you want Tim to respond.",
                inline=False
            )
        
        await ctx.respond(embed=embed)
        
    except Exception as e:
        logger.error(f"Error getting chat status: {e}")
        await ctx.respond("Failed to get chat status. Please try again.", flags=hikari.MessageFlag.EPHEMERAL)

@arc.loader
def load(client: arc.GatewayClient) -> None:
    """Load the chat plugin."""
    client.add_plugin(plugin)

@arc.unloader
def unload(client: arc.GatewayClient) -> None:
    """Unload the chat plugin."""
    client.remove_plugin(plugin)
"""
Round leaderboard - shows current player positions during a round.
"""
from typing import List, Dict, Optional, Tuple
from database.session import db_session
from database.models import GamePlayer, Answer, User, Round
from utils.logging import get_logger

logger = get_logger(__name__)


def get_round_leaderboard(game_id: int, round_id: int, current_user_id: int = None) -> Tuple[str, Optional[int]]:
    """
    Get current round leaderboard text and player position.
    
    Args:
        game_id: Game ID
        round_id: Round ID
        current_user_id: Optional current user ID to highlight
        
    Returns:
        Tuple of (leaderboard_text, player_position)
        Returns ("", None) if error or no data
    """
    try:
        with db_session() as session:
            # Get all alive players
            players = session.query(GamePlayer).filter(
                GamePlayer.game_id == game_id,
                GamePlayer.is_eliminated == False
            ).all()
            
            if not players:
                return "", None
            
            # Get current round answers for each player
            player_scores = []
            for player in players:
                # Count correct answers in current round
                correct_count = session.query(Answer).filter(
                    Answer.round_id == round_id,
                    Answer.user_id == player.user_id,
                    Answer.is_correct == True
                ).count()
                
                # Get user name
                user = session.query(User).filter(User.id == player.user_id).first()
                if user:
                    player_name = user.full_name or user.username or f"User {user.id}"
                    player_scores.append({
                        'user_id': player.user_id,
                        'name': player_name,
                        'score': correct_count,
                        'is_bot': player.is_bot
                    })
            
            if not player_scores:
                return "", None
            
            # Sort by score (descending), then by name (ascending) for tie-breaking
            player_scores.sort(key=lambda x: (-x['score'], x['name'].lower()))
            
            # Find current player position
            player_position = None
            if current_user_id:
                for i, player in enumerate(player_scores, 1):
                    if player['user_id'] == current_user_id:
                        player_position = i
                        break
            
            # Build leaderboard text (top 10 or all if less than 10)
            leaderboard_lines = ["📊 **Текущие результаты раунда:**\n"]
            
            top_players = player_scores[:10]  # Top 10
            for i, player in enumerate(top_players, 1):
                medal = ""
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                
                # Highlight current user
                marker = "👤 " if player['user_id'] == current_user_id else ""
                bot_marker = "🤖 " if player['is_bot'] else ""
                
                leaderboard_lines.append(
                    f"{medal} {i}. {marker}{bot_marker}{player['name']}: {player['score']} ✅"
                )
            
            # Add current player position if not in top 10
            if current_user_id and player_position and player_position > 10:
                current_player = next((p for p in player_scores if p['user_id'] == current_user_id), None)
                if current_player:
                    leaderboard_lines.append(f"\n**Ваше место:** #{player_position} ({current_player['score']} ✅)")
            
            return "\n".join(leaderboard_lines), player_position
            
    except Exception as e:
        logger.error(f"Error getting round leaderboard: {e}", exc_info=True)
        return "", None

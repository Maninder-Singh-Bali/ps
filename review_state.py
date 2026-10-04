"""Current output review and historical decisions, independent of approval gates."""
from datetime import datetime, timezone


def transition(asset, decision, note=''):
    if decision not in ('kept', 'approved', 'rejected'):
        raise ValueError('Unknown review decision.')
    history = asset.setdefault('review_history', [])
    history.append({'status': asset.get('status', 'review'),
                    'decision': asset.get('review_decision'),
                    'note': asset.get('review_note', ''),
                    'recorded_at': datetime.now(timezone.utc).isoformat()})
    asset['status'] = 'review' if decision == 'kept' else decision
    asset['review_decision'] = decision
    asset['review_note'] = ('Kept for review — not approved.' if decision == 'kept'
                            else note if decision == 'rejected' else 'Approved.')

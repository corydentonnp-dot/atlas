#!/usr/bin/env python
import yaml

with open('docs/workflow_prioritization.yaml') as f:
    data = yaml.safe_load(f)

workflows = sorted(data['workflows'], key=lambda x: x['quick_win_score'], reverse=True)

print('TOP 20 WORKFLOWS BY QUICK_WIN_SCORE:\n')
for w in workflows[:20]:
    print(f"{w['id']:3d}. {w['name']:40s} | Score: {w['quick_win_score']:2d} | Phase: {w['recommended_phase']}")

print('\n\nTOP 15 PRIORITY ITEMS (excluding already completed workflows):')
print('Completed so far: rent_reminder (29), maintenance_intake (26), shared_expense (31), promo_apr (35), filing_deadline (76)')
top_15 = []
for w in workflows:
    if w['name'] not in ['rent_reminder_agent', 'maintenance_intake_agent', 'shared_expense_classifier', 
                         'promo_apr_deadline_agent', 'filing_deadline_tracker']:
        top_15.append(w)
    if len(top_15) == 15:
        break

print('\nTOP 15 TODO:\n')
for i, w in enumerate(top_15, 1):
    print(f"{i:2d}. {w['name']:40s} | Score: {w['quick_win_score']:2d} | Phase: {w['recommended_phase']}")

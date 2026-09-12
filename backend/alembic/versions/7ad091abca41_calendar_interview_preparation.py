"""Persist account calendar events and versioned interview preparation.

Revision ID: 7ad091abca41
Revises: 524a1fa660af
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = '7ad091abca41'
down_revision = '524a1fa660af'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('calendar_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('jobs.id', ondelete='SET NULL')),
        sa.Column('title', sa.String(250), nullable=False), sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time', sa.String(5), nullable=False), sa.Column('type', sa.String(20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False), sa.Column('timezone', sa.String(100), nullable=False),
        sa.Column('starts_at', sa.DateTime(timezone=True)), sa.Column('revision', sa.Integer(), nullable=False))
    op.create_index('ix_calendar_events_user_id', 'calendar_events', ['user_id'])
    op.create_table('interview_preps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_id', sa.String(36), sa.ForeignKey('calendar_events.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False),
        sa.Column('source_fingerprint', sa.String(64), nullable=False),
        sa.Column('settings', postgresql.JSONB(), nullable=False), sa.Column('content', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('user_id', 'request_id', name='uq_prep_request'))
    op.create_index('ix_interview_preps_user_id', 'interview_preps', ['user_id'])
    op.create_index('ix_interview_preps_event_id', 'interview_preps', ['event_id'])
    op.create_table('prep_messages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('interview_preps.id', ondelete='CASCADE'), nullable=False),
        sa.Column('request_id', sa.String(36), nullable=False), sa.Column('role', sa.String(12), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('plan_id', 'request_id', 'role', name='uq_prep_message_request'))
    op.create_index('ix_prep_messages_plan_id', 'prep_messages', ['plan_id'])


def downgrade():
    op.drop_table('prep_messages')
    op.drop_table('interview_preps')
    op.drop_table('calendar_events')

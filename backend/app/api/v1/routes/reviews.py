from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.models import CaregiverProfile, Conversation, Review, User
from backend.app.db.session import get_db
from backend.app.schemas.reviews import ReviewCreate, ReviewRead, ReviewUpdate, TrustSummaryRead
from backend.app.services.sms import SmsNotificationService

router = APIRouter()


def _get_user(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _get_review(db: Session, review_id: str) -> Review:
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
    return review


def _get_conversation(db: Session, conversation_id: str) -> Conversation:
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if conversation.kind != "care_chat":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only care chat conversations can be reviewed")
    return conversation


def _validate_review_pair(conversation: Conversation, reviewer_id: str, reviewee_id: str) -> None:
    def normalize(value: str | None) -> str:
        return (value or "").replace("-", "").lower()

    participants = {normalize(conversation.participant_a), normalize(conversation.participant_b)}
    reviewer = normalize(reviewer_id)
    reviewee = normalize(reviewee_id)
    if "" in participants or reviewer not in participants or reviewee not in participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reviewer and reviewee must be participants in the matched conversation",
        )
    if reviewer == reviewee:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reviewer and reviewee cannot be the same")


def _refresh_caregiver_rating(db: Session, user_id: str) -> None:
    profile = db.query(CaregiverProfile).filter(CaregiverProfile.user_id == user_id).first()
    if not profile:
        return
    rating = db.query(func.coalesce(func.avg(Review.score), 0)).filter(Review.reviewee_id == user_id).scalar()
    profile.rating_avg = float(rating or 0)


def _trust_summary(db: Session, user_id: str) -> TrustSummaryRead:
    _get_user(db, user_id)
    review_count, rating_avg = (
        db.query(func.count(Review.id), func.coalesce(func.avg(Review.score), 0))
        .filter(Review.reviewee_id == user_id)
        .one()
    )
    recent_reviews = (
        db.query(Review)
        .filter(Review.reviewee_id == user_id)
        .order_by(Review.created_at.desc())
        .limit(10)
        .all()
    )
    return TrustSummaryRead(
        user_id=user_id,
        rating_avg=float(rating_avg or 0),
        review_count=int(review_count or 0),
        recent_reviews=recent_reviews,
    )


async def _notify_reviewee(db: Session, review: Review) -> None:
    user = db.query(User).filter(User.id == review.reviewee_id).first()
    if not user or not user.phone:
        return
    await SmsNotificationService().create_and_send(
        db,
        scene="new_review",
        user_id=user.id,
        phone=user.phone,
        payload={
            "conversation_id": review.conversation_id,
            "reviewer_id": review.reviewer_id,
            "score": review.score,
        },
    )


@router.post("", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def create_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> Review:
    _get_user(db, payload.reviewer_id)
    _get_user(db, payload.reviewee_id)
    conversation = _get_conversation(db, payload.conversation_id)
    _validate_review_pair(conversation, payload.reviewer_id, payload.reviewee_id)

    existing = (
        db.query(Review)
        .filter(Review.conversation_id == payload.conversation_id, Review.reviewer_id == payload.reviewer_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reviewer already submitted a review")

    review = Review(**payload.model_dump())
    db.add(review)
    db.flush()
    _refresh_caregiver_rating(db, payload.reviewee_id)
    db.commit()
    db.refresh(review)
    await _notify_reviewee(db, review)
    return review


@router.get("", response_model=list[ReviewRead])
async def list_reviews(
    conversation_id: str | None = None,
    user_id: str | None = Query(default=None, description="Reviews received by this user"),
    reviewer_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[Review]:
    query = db.query(Review)
    if conversation_id:
        query = query.filter(Review.conversation_id == conversation_id)
    if user_id:
        query = query.filter(Review.reviewee_id == user_id)
    if reviewer_id:
        query = query.filter(Review.reviewer_id == reviewer_id)
    return query.order_by(Review.created_at.desc()).limit(100).all()


@router.get("/trust/{user_id}", response_model=TrustSummaryRead)
async def get_trust_summary(user_id: str, db: Session = Depends(get_db)) -> TrustSummaryRead:
    return _trust_summary(db, user_id)


@router.get("/conversations/{conversation_id}", response_model=list[ReviewRead])
async def list_conversation_reviews(conversation_id: str, db: Session = Depends(get_db)) -> list[Review]:
    _get_conversation(db, conversation_id)
    return (
        db.query(Review)
        .filter(Review.conversation_id == conversation_id)
        .order_by(Review.created_at.desc())
        .all()
    )


@router.put("/{review_id}", response_model=ReviewRead)
async def update_review(
    review_id: str,
    payload: ReviewUpdate,
    reviewer_id: str = Query(...),
    db: Session = Depends(get_db),
) -> Review:
    review = _get_review(db, review_id)
    if review.reviewer_id != reviewer_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the reviewer can update this review")
    review.score = payload.score
    review.tags = payload.tags
    review.comment = payload.comment
    _refresh_caregiver_rating(db, review.reviewee_id)
    db.commit()
    db.refresh(review)
    return review

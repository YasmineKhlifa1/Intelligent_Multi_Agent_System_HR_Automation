import asyncio
from datetime import datetime, timedelta
import logging
import json
import os
from current.Crews.Gmail_Crew import CrewContext as EmailCrewContext
from Agents.CAgent_D import CrewContext as CalendarCrewContext
from current.Crews.Linkedin_Crew import LinkedInCrewContext
from current.db import get_mongo_db
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from current.Services.Gmail_D import send_reply

logger = logging.getLogger(__name__)
mongo_db = get_mongo_db()
scheduler_manager = AsyncIOScheduler()

async def scheduled_crew_job(user_id: int, crew_id: int):
    """Asynchronous logic to handle crew execution and logging for email, calendar, and LinkedIn crews."""
    try:
        logger.info(f"Starting job for user {user_id}, crew {crew_id}")
        
        # Get crew details from DB
        crew = await mongo_db.get_crew(crew_id)
        if not crew:
            logger.error(f"Crew {crew_id} not found for user {user_id}")
            return
        
        # Handle crew type migration for legacy 'email' type
        if crew.get('crew_type') == "email":
            try:
                update_success = await mongo_db.update_crew(crew_id, {"crew_type": "email_scoring"})
                if update_success:
                    logger.info(f"Migrated crew {crew_id} from 'email' to 'email_scoring'")
                    crew['crew_type'] = "email_scoring"
                else:
                    logger.error(f"Failed to migrate crew {crew_id}")
                    return
            except Exception as e:
                logger.error(f"Migration error for crew {crew_id}: {e}")
                return
        
        # Verify we have a valid crew type
        crew_type = crew.get('crew_type')
        if not crew_type:
            logger.error(f"Crew {crew_id} has no type defined")
            return
            
        # Create appropriate context based on crew type
        if crew_type in ["email_scoring", "email_reply"]:
            crew_context = EmailCrewContext(user_id)
        elif crew_type == "calendar":
            crew_context = CalendarCrewContext(user_id)
        elif crew_type == "linkedin-content":
            crew_context = LinkedInCrewContext(user_id)
        else:
            logger.error(f"Unsupported crew type: {crew_type}")
            return
        
        # Create crew instance based on crew type
        if crew_type == "email_scoring":
            crew_instance = crew_context.create_scoring_crew()
        elif crew_type == "email_reply":
            crew_instance = crew_context.create_reply_crew()
        elif crew_type == "calendar":
            crew_instance = crew_context.create_calendar_crew()
        elif crew_type == "linkedin-content":
            crew_instance = crew_context.create_content_crew()
        else:
            logger.error(f"Unexpected crew type: {crew_type}")
            return
        
        # Prepare inputs for crew execution
        inputs = {}
        if crew_type == "linkedin-content":
            try:
                scrape_file_path = crew.get('scrape_file_path', 'scraped_content.txt')
                if not os.path.exists(scrape_file_path):
                    logger.error(f"Scraped content file not found: {scrape_file_path}")
                    raise FileNotFoundError(f"Scraped content file not found: {scrape_file_path}")
                
                with open(scrape_file_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                if not text:
                    logger.error(f"Scraped content file is empty: {scrape_file_path}")
                    raise ValueError(f"Scraped content file is empty: {scrape_file_path}")
                
                field ="AI"
                inputs = {'text': text ,'field': field}
                logger.info(f"Loaded scraped content for crew {crew_id} from {scrape_file_path}")
            except Exception as e:
                logger.error(f"Failed to load scraped content for crew {crew_id}: {str(e)}", exc_info=True)
                await mongo_db.log_execution({
                    "timestamp": datetime.utcnow(),
                    "user_id": user_id,
                    "crew_id": crew_id,
                    "error": f"Failed to load scraped content: {str(e)}"
                })
                return
        
        # Execute crew
        try:
            if hasattr(crew_instance, 'kickoff_async'):
                logger.info(f"Executing crew {crew_id} with kickoff_async, inputs={bool(inputs)}")
                result = await crew_instance.kickoff_async(inputs=inputs)
            else:
                logger.info(f"Executing crew {crew_id} with kickoff, inputs={bool(inputs)}")
                result = crew_instance.kickoff(inputs=inputs)
        except Exception as e:
            logger.error(f"Crew execution failed for crew {crew_id}: {str(e)}", exc_info=True)
            raise

        logger.info(f"Crew {crew_id} executed successfully, result: {result}")

        # Log execution
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow(),
            "user_id": user_id,
            "crew_id": crew_id,
            "result": json.dumps(result, default=str)
        })
        
    except Exception as e:
        logger.error(f"Job failed for user {user_id}, crew {crew_id}: {str(e)}", exc_info=True)
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow(),
            "user_id": user_id,
            "crew_id": crew_id,
            "error": str(e)
        })

async def process_emails_with_scoring_and_reply(user_id: int):
    """Process emails by scoring urgency and handling replies or scheduling follow-ups."""
    try:
        logger.info(f"Starting email processing for user {user_id}")
        
        # Start scheduler if not running
        if not scheduler_manager.running:
            scheduler_manager.start()
            logger.info("Started AsyncIOScheduler for email follow-ups")
        
        # Find or create scoring crew
        crews = await mongo_db.get_user_crews(user_id)
        scoring_crew = next((crew for crew in crews if crew.crew_type == 'email_scoring'), None)
        if not scoring_crew:
            scoring_crew_id = await mongo_db.add_crew(user_id, {
                'crew_type': 'email_scoring',
                'created_at': datetime.utcnow(),
                'schedule': {}
            })
            logger.info(f"Created new email_scoring crew with ID {scoring_crew_id} for user {user_id}")
        else:
            scoring_crew_id = scoring_crew.crew_id
        
        # Execute scoring crew
        crew_context = EmailCrewContext(user_id)
        scoring_crew_instance = crew_context.create_scoring_crew()
        
        try:
            logger.debug(f"Executing scoring crew {scoring_crew_id} for user {user_id}")
            if hasattr(scoring_crew_instance, 'kickoff_async'):
                scoring_result = await scoring_crew_instance.kickoff_async(inputs={})
            else:
                scoring_result = crew_context.create_scoring_crew().kickoff(inputs={})
            logger.debug(f"Scoring crew result: {scoring_result}")
        except Exception as e:
            logger.error(f"Scoring crew {scoring_crew_id} failed for user {user_id}: {str(e)}", exc_info=True)
            await mongo_db.log_execution({
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "crew_id": scoring_crew_id,
                "error": str(e)
            })
            return
        
        logger.info(f"Scoring crew {scoring_crew_id} executed successfully")
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "crew_id": scoring_crew_id,
            "result": json.dumps(scoring_result, default=str)
        })
        
        # Parse scoring result
        try:
            result_model = scoring_result.pydantic if hasattr(scoring_result, 'pydantic') else json.loads(scoring_result)
            if isinstance(result_model, dict):
                scored_emails = result_model.get('retrieved_emails', [])
            else:
                scored_emails = [email_score.dict() for email_score in result_model.scores]
            if not scored_emails:
                logger.warning(f"No emails scored by crew {scoring_crew_id} for user {user_id}")
                return
            logger.debug(f"Scored emails: {json.dumps(scored_emails, default=str)}")
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Failed to parse scoring result for crew {scoring_crew_id}: {str(e)}", exc_info=True)
            await mongo_db.log_execution({
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "crew_id": scoring_crew_id,
                "error": f"Invalid scoring result format: {str(e)}"
            })
            return
        
        # Find or create reply crew
        reply_crew = next((crew for crew in crews if crew.crew_type == 'email_reply'), None)
        if not reply_crew:
            reply_crew_id = await mongo_db.add_crew(user_id, {
                'crew_type': 'email_reply',
                'created_at': datetime.utcnow(),
                'schedule': {}
            })
            logger.info(f"Created new email_reply crew with ID {reply_crew_id} for user {user_id}")
        else:
            reply_crew_id = reply_crew.crew_id
        
        # Process each scored email
        for email in scored_emails:
            email_score = email.get('urgency_score', 0)
            email_id = email.get('id', str(hash(email.get('body', '')[:100])))
            logger.info(f"Processing email ID {email_id} with score {email_score}")
            
            if email_score < 5:
                await handle_urgent_email(email, crew_context, reply_crew_id, user_id)
            else:
                await schedule_followup(email, crew_context, reply_crew_id, user_id)
        
    except Exception as e:
        logger.error(f"Email processing failed for user {user_id}: {str(e)}", exc_info=True)
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "crew_id": None,
            "error": str(e)
        })

async def handle_urgent_email(email: dict, crew_context: EmailCrewContext, reply_crew_id: int, user_id: int):
    """Handle immediate reply for emails with urgency score < 5."""
    try:
        email_id = email.get('id', 'unknown')
        email_score = email.get('urgency_score', 0)
        logger.debug(f"Handling urgent email {email_id} with score {email_score} for user {user_id}")
        
        reply_crew_instance = crew_context.create_reply_crew()
        reply_inputs = {"context": email.get('body', '')}
        
        try:
            logger.debug(f"Executing reply crew {reply_crew_id} for email {email_id} with inputs: {reply_inputs}")
            if hasattr(reply_crew_instance, 'kickoff_async'):
                reply_result = await reply_crew_instance.kickoff_async(inputs=reply_inputs)
            else:
                reply_result = reply_crew_instance.kickoff(inputs=reply_inputs)
            logger.debug(f"Reply crew result: {reply_result}")
        except Exception as e:
            logger.error(f"Reply crew {reply_crew_id} failed for email {email_id}: {str(e)}", exc_info=True)
            await mongo_db.log_execution({
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "crew_id": reply_crew_id,
                "error": f"Failed to generate reply for email {email_id}: {str(e)}"
            })
            return
        
        # Parse reply
        try:
            reply_model = reply_result.pydantic if hasattr(reply_result, 'pydantic') else json.loads(reply_result)
            if isinstance(reply_model, dict):
                replies = reply_model.get('reply', [])
            else:
                replies = reply_model.reply
            if not replies:
                logger.warning(f"No reply generated for email {email_id}")
                await mongo_db.log_execution({
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "crew_id": reply_crew_id,
                    "result": f"No reply generated for email {email_id}"
                })
                return
            
            # Assume first reply
            reply = replies[0].model_dump() if isinstance(replies, list) else replies.model_dump()
            reply_subject = f"Re: {email.get('subject', 'No Subject')}"
            reply_body = reply.get('body', '')
            reply_to = email.get('from', '')
            
            logger.debug(f"Sending reply for email {email_id}: to={reply_to}, subject={reply_subject}, body={reply_body[:50]}...")
            # Send reply
            success = await send_reply(user_id, reply_to, reply_subject, reply_body)
            if success:
                logger.info(f"Sent reply for email ID {email_id}")
                await mongo_db.log_execution({
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "crew_id": reply_crew_id,
                    "result": f"Sent reply for email {email_id}"
                })
            else:
                logger.error(f"Failed to send reply for email {email_id}: send_reply returned False")
                await mongo_db.log_execution({
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "crew_id": reply_crew_id,
                    "error": f"Failed to send reply for email {email_id}: send_reply returned False"
                })
        except Exception as e:
            logger.error(f"Failed to process reply for email {email_id}: {str(e)}", exc_info=True)
            await mongo_db.log_execution({
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "crew_id": reply_crew_id,
                "error": f"Failed to process reply for email {email_id}: {str(e)}"
            })
            
    except Exception as e:
        logger.error(f"Failed to handle urgent email {email_id}: {str(e)}", exc_info=True)
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "crew_id": reply_crew_id,
            "error": f"Failed to handle urgent email {email_id}: {str(e)}"
        })

async def schedule_followup(email: dict, crew_context: EmailCrewContext, reply_crew_id: int, user_id: int):
    """Schedule follow-up for emails with urgency score >= 5."""
    try:
        email_id = email.get('id', str(hash(email.get('body', '')[:100])))
        email_score = email.get('urgency_score', 0)
        logger.debug(f"Scheduling follow-up for email {email_id} with score {email_score} for user {user_id}")
        
        from email.utils import parsedate_to_datetime
        date_str = email.get('date', '')
        if date_str:
            try:
                email_date = parsedate_to_datetime(date_str)
                followup_time = email_date + timedelta(hours=2)
            except (ValueError, TypeError):
                followup_time = datetime.now().astimezone() + timedelta(hours=2)
        else:
            followup_time = datetime.now().astimezone() + timedelta(hours=2)
        
        def job_func():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            reply_crew_instance = crew_context.create_reply_crew()
            reply_inputs = {"context": email.get('body', '')}
            try:
                logger.debug(f"Executing scheduled reply crew {reply_crew_id} for email {email_id}")
                if hasattr(reply_crew_instance, 'kickoff_async'):
                    reply_result = loop.run_until_complete(reply_crew_instance.kickoff_async(inputs=reply_inputs))
                else:
                    reply_result = loop.run_until_complete(reply_crew_instance.kickoff(inputs=reply_inputs))
                
                reply_model = reply_result.pydantic if hasattr(reply_result, 'pydantic') else json.loads(reply_result)
                if isinstance(reply_model, dict):
                    replies = reply_model.get('reply', [])
                else:
                    replies = reply_model.reply
                if not replies:
                    logger.warning(f"No reply generated for scheduled email {email_id}")
                    loop.run_until_complete(mongo_db.log_execution({
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_id": user_id,
                        "crew_id": reply_crew_id,
                        "result": f"No reply generated for scheduled email {email_id}"
                    }))
                    return
                
                reply = replies[0].model_dump() if isinstance(replies, list) else replies.model_dump()
                reply_subject = f"Re: {email.get('subject', 'No Subject')}"
                reply_body = reply.get('body', '')
                reply_to = email.get('from', '')
                
                success = loop.run_until_complete(
                    send_reply(user_id, reply_to, reply_subject, reply_body)
                )
                if success:
                    logger.info(f"Sent scheduled reply for email ID {email_id}")
                    loop.run_until_complete(mongo_db.log_execution({
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_id": user_id,
                        "crew_id": reply_crew_id,
                        "result": f"Sent scheduled reply for email {email_id}"
                    }))
                else:
                    logger.error(f"Failed to send scheduled reply for email {email_id}: send_reply returned False")
                    loop.run_until_complete(mongo_db.log_execution({
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_id": user_id,
                        "crew_id": reply_crew_id,
                        "error": f"Failed to send scheduled reply for email {email_id}: send_reply returned False"
                    }))
            except Exception as e:
                logger.error(f"Scheduled reply failed for email {email_id}: {str(e)}", exc_info=True)
                loop.run_until_complete(mongo_db.log_execution({
                    "timestamp": datetime.utcnow().isoformat(),
                    "user_id": user_id,
                    "crew_id": reply_crew_id,
                    "error": f"Scheduled reply failed for email {email_id}: {str(e)}"
                }))
            finally:
                loop.close()
        
        scheduler_manager.add_job(
            job_func,
            trigger=DateTrigger(run_date=followup_time),
            id=f"email_followup_{email_id}",
            replace_existing=True
        )
        logger.info(f"Scheduled follow-up for email ID {email_id} at {followup_time}")
        
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "crew_id": reply_crew_id,
            "result": f"Scheduled follow-up for email {email_id} at {followup_time}"
        })
        
    except Exception as e:
        logger.error(f"Failed to schedule follow-up for email {email_id}: {str(e)}", exc_info=True)
        await mongo_db.log_execution({
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "crew_id": reply_crew_id,
            "error": f"Failed to schedule follow-up for email {email_id}: {str(e)}"
        })
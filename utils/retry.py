import asyncio
import logging
from typing import Callable, Any, Optional
import random

logger = logging.getLogger(__name__)

async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    **kwargs
) -> Any:
    """
    Retry a function with exponential backoff and jitter
    
    Args:
        func: The function to retry
        *args: Arguments to pass to the function
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The result of the successful function call
    
    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # Try to execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success! Log if this wasn't the first attempt
            if attempt > 0:
                logger.info(f"Function {func.__name__} succeeded after {attempt} retries")
            
            return result
            
        except Exception as e:
            last_exception = e
            
            # If this was the last attempt, don't delay
            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} retries. Last error: {str(e)}")
                break
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (exponential_base ** attempt), max_delay)
            
            # Add jitter to prevent thundering herd
            if jitter:
                delay *= (0.5 + random.random() * 0.5)
            
            logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}, retrying in {delay:.2f}s. Error: {str(e)}")
            
            # Wait before retrying
            await asyncio.sleep(delay)
    
    # If we get here, all retries failed
    raise last_exception

async def retry_with_conditions(
    func: Callable,
    *args,
    max_retries: int = 3,
    retry_on: Optional[list] = None,
    no_retry_on: Optional[list] = None,
    base_delay: float = 1.0,
    **kwargs
) -> Any:
    """
    Retry a function with specific exception conditions
    
    Args:
        func: The function to retry
        *args: Arguments to pass to the function
        max_retries: Maximum number of retry attempts
        retry_on: List of exception types to retry on
        no_retry_on: List of exception types to NOT retry on
        base_delay: Delay between retries in seconds
        **kwargs: Keyword arguments to pass to the function
    
    Returns:
        The result of the successful function call
    
    Raises:
        The last exception if all retries fail or if exception is in no_retry_on
    """
    if retry_on is None:
        retry_on = [Exception]
    
    if no_retry_on is None:
        no_retry_on = []
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # Try to execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success!
            if attempt > 0:
                logger.info(f"Function {func.__name__} succeeded after {attempt} retries")
            
            return result
            
        except Exception as e:
            last_exception = e
            
            # Check if this exception should not be retried
            if any(isinstance(e, exc_type) for exc_type in no_retry_on):
                logger.error(f"Function {func.__name__} failed with non-retryable exception: {str(e)}")
                raise e
            
            # Check if this exception should be retried
            if not any(isinstance(e, exc_type) for exc_type in retry_on):
                logger.error(f"Function {func.__name__} failed with non-retryable exception type: {str(e)}")
                raise e
            
            # If this was the last attempt, don't delay
            if attempt == max_retries:
                logger.error(f"Function {func.__name__} failed after {max_retries} retries. Last error: {str(e)}")
                break
            
            logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}, retrying in {base_delay}s. Error: {str(e)}")
            
            # Wait before retrying
            await asyncio.sleep(base_delay)
    
    # If we get here, all retries failed
    raise last_exception

class CircuitBreaker:
    """Simple circuit breaker implementation for retry logic"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call a function through the circuit breaker"""
        
        # Check if circuit should be closed or half-open
        if self.state == "open":
            if self.last_failure_time and (asyncio.get_event_loop().time() - self.last_failure_time) > self.recovery_timeout:
                self.state = "half-open"
                logger.info("Circuit breaker moving to half-open state")
            else:
                raise Exception("Circuit breaker is open - too many recent failures")
        
        try:
            # Try to execute the function
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # Success - reset circuit breaker
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
                logger.info("Circuit breaker closed after successful call")
            
            return result
            
        except Exception as e:
            # Failure - update circuit breaker state
            self.failure_count += 1
            self.last_failure_time = asyncio.get_event_loop().time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
            
            raise e

# Global circuit breakers for different services
circuit_breakers = {
    "gemini_api": CircuitBreaker(failure_threshold=3, recovery_timeout=30.0),
    "webhook": CircuitBreaker(failure_threshold=5, recovery_timeout=60.0),
    "database": CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
}

async def retry_with_circuit_breaker(
    func: Callable,
    service_name: str,
    *args,
    max_retries: int = 3,
    **kwargs
) -> Any:
    """Retry a function with circuit breaker protection"""
    
    circuit_breaker = circuit_breakers.get(service_name)
    if not circuit_breaker:
        # No circuit breaker configured, use regular retry
        return await retry_with_backoff(func, *args, max_retries=max_retries, **kwargs)
    
    # Use circuit breaker with retry
    async def protected_func(*args, **kwargs):
        return await circuit_breaker.call(func, *args, **kwargs)
    
    return await retry_with_backoff(protected_func, *args, max_retries=max_retries, **kwargs)

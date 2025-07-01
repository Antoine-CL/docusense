"""
AllFind Telemetry Module
Implements ChatGPT's best-practice logging for production monitoring
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps
import json

# Application Insights integration
try:
    from opencensus.ext.azure.log_exporter import AzureLogHandler
    from opencensus.ext.azure.metrics_exporter import new_metrics_exporter
    from opencensus.stats import aggregation as aggregation_module
    from opencensus.stats import measure as measure_module
    from opencensus.stats import stats as stats_module
    from opencensus.stats import view as view_module
    from opencensus.tags import tag_map as tag_map_module
    AZURE_LOGGING_AVAILABLE = True
except ImportError:
    AZURE_LOGGING_AVAILABLE = False
    print("⚠️  Azure logging not available. Install: pip install opencensus-ext-azure")

class AllFindLogger:
    """Enhanced logger with Application Insights integration"""
    
    def __init__(self, name: str = "docusense"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Application Insights connection
        self.connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
        self.metrics_exporter = None
        
        if AZURE_LOGGING_AVAILABLE and self.connection_string:
            self._setup_azure_logging()
            self._setup_metrics()
        else:
            self._setup_console_logging()
    
    def _setup_azure_logging(self):
        """Setup Azure Application Insights logging"""
        try:
            azure_handler = AzureLogHandler(connection_string=self.connection_string)
            azure_handler.setLevel(logging.INFO)
            
            # Custom formatter for structured logging
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            azure_handler.setFormatter(formatter)
            
            self.logger.addHandler(azure_handler)
            self.logger.info("Azure Application Insights logging initialized")
            
        except Exception as e:
            print(f"Failed to setup Azure logging: {e}")
            self._setup_console_logging()
    
    def _setup_console_logging(self):
        """Fallback to console logging"""
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(console_handler)
    
    def _setup_metrics(self):
        """Setup custom metrics for Application Insights"""
        if not AZURE_LOGGING_AVAILABLE or not self.connection_string:
            return
        
        try:
            self.metrics_exporter = new_metrics_exporter(
                connection_string=self.connection_string
            )
            
            # Define custom measures
            self.indexing_duration_measure = measure_module.MeasureFloat(
                "IndexingDurationMs", "Time taken to index a document", "ms"
            )
            
            self.file_size_measure = measure_module.MeasureInt(
                "FileSizeBytes", "Size of processed file", "bytes"
            )
            
            self.embedding_cost_measure = measure_module.MeasureFloat(
                "EmbeddingCostUSD", "Cost of embedding generation", "USD"
            )
            
            # Create views for metrics
            stats = stats_module.stats
            view_manager = stats.view_manager
            
            indexing_view = view_module.View(
                "IndexingDuration",
                "Average indexing duration",
                [],
                self.indexing_duration_measure,
                aggregation_module.LastValueAggregation()
            )
            
            file_size_view = view_module.View(
                "FileSize",
                "File size distribution",
                [],
                self.file_size_measure,
                aggregation_module.LastValueAggregation()
            )
            
            cost_view = view_module.View(
                "EmbeddingCost",
                "Embedding generation cost",
                [],
                self.embedding_cost_measure,
                aggregation_module.SumAggregation()
            )
            
            view_manager.register_view(indexing_view)
            view_manager.register_view(file_size_view)
            view_manager.register_view(cost_view)
            
            # Setup exporter
            view_manager.register_exporter(self.metrics_exporter)
            
        except Exception as e:
            print(f"Failed to setup metrics: {e}")
    
    def track_metric(self, name: str, value: float, properties: Optional[Dict[str, str]] = None):
        """Track a custom metric"""
        if self.metrics_exporter:
            try:
                stats = stats_module.stats
                mmap = stats.stats_recorder.new_measurement_map()
                tmap = tag_map_module.TagMap()
                
                if name == "IndexingDurationMs":
                    mmap.measure_float_put(self.indexing_duration_measure, value)
                elif name == "FileSizeBytes":
                    mmap.measure_int_put(self.file_size_measure, int(value))
                elif name == "EmbeddingCostUSD":
                    mmap.measure_float_put(self.embedding_cost_measure, value)
                
                mmap.record(tmap)
                
            except Exception as e:
                self.logger.warning(f"Failed to track metric {name}: {e}")
    
    def log_file_processing(self, event: str, file_meta: Dict[str, Any], 
                          duration_ms: Optional[float] = None, 
                          error: Optional[Exception] = None):
        """Log file processing events with structured data"""
        
        custom_dimensions = {
            "event_type": "file_processing",
            "file_name": file_meta.get("file_name", "unknown"),
            "file_size": file_meta.get("file_size", 0),
            "tenant_id": file_meta.get("tenant_id", "unknown"),
            "drive_id": file_meta.get("drive_id", "unknown"),
            "item_id": file_meta.get("item_id", "unknown"),
            "processing_method": file_meta.get("processing_method", "standard")
        }
        
        if duration_ms:
            custom_dimensions["duration_ms"] = duration_ms
            self.track_metric("IndexingDurationMs", duration_ms)
        
        if file_meta.get("file_size"):
            self.track_metric("FileSizeBytes", file_meta["file_size"])
        
        if file_meta.get("estimated_cost"):
            custom_dimensions["estimated_cost_usd"] = file_meta["estimated_cost"]
            self.track_metric("EmbeddingCostUSD", file_meta["estimated_cost"])
        
        if error:
            self.logger.error(
                f"file_processing_failed: {event}",
                extra={"custom_dimensions": custom_dimensions},
                exc_info=error
            )
        else:
            self.logger.info(
                f"file_processing_success: {event}",
                extra={"custom_dimensions": custom_dimensions}
            )
    
    def log_webhook_event(self, event: str, notification_data: Dict[str, Any], 
                         error: Optional[Exception] = None):
        """Log webhook processing events"""
        
        custom_dimensions = {
            "event_type": "webhook",
            "subscription_id": notification_data.get("subscriptionId", "unknown"),
            "resource": notification_data.get("resource", "unknown"),
            "change_type": notification_data.get("changeType", "unknown"),
            "tenant_id": notification_data.get("tenantId", "unknown")
        }
        
        if error:
            self.logger.error(
                f"webhook_failed: {event}",
                extra={"custom_dimensions": custom_dimensions},
                exc_info=error
            )
        else:
            self.logger.info(
                f"webhook_success: {event}",
                extra={"custom_dimensions": custom_dimensions}
            )
    
    def log_search_query(self, query: str, tenant_id: str, result_count: int, 
                        duration_ms: float):
        """Log search query performance"""
        
        custom_dimensions = {
            "event_type": "search_query",
            "tenant_id": tenant_id,
            "query_length": len(query),
            "result_count": result_count,
            "duration_ms": duration_ms
        }
        
        self.logger.info(
            "search_query_executed",
            extra={"custom_dimensions": custom_dimensions}
        )
    
    def log_queue_event(self, event: str, queue_name: str, message_count: int):
        """Log queue processing events"""
        
        custom_dimensions = {
            "event_type": "queue",
            "queue_name": queue_name,
            "message_count": message_count
        }
        
        self.logger.info(
            f"queue_event: {event}",
            extra={"custom_dimensions": custom_dimensions}
        )

# Global logger instance
logger = AllFindLogger()

def track_performance(operation_name: str):
    """Decorator to track operation performance"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation_success = False
            error = None
            
            try:
                result = func(*args, **kwargs)
                operation_success = True
                return result
            except Exception as e:
                error = e
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                custom_dimensions = {
                    "operation": operation_name,
                    "duration_ms": duration_ms,
                    "success": operation_success
                }
                
                if error:
                    logger.logger.error(
                        f"operation_failed: {operation_name}",
                        extra={"custom_dimensions": custom_dimensions},
                        exc_info=error
                    )
                else:
                    logger.logger.info(
                        f"operation_completed: {operation_name}",
                        extra={"custom_dimensions": custom_dimensions}
                    )
                
                # Track performance metric
                logger.track_metric(f"{operation_name}DurationMs", duration_ms)
        
        return wrapper
    return decorator

# Convenience functions
def log_info(message: str, **kwargs):
    """Log info message with optional custom dimensions"""
    logger.logger.info(message, extra={"custom_dimensions": kwargs} if kwargs else None)

def log_error(message: str, error: Optional[Exception] = None, **kwargs):
    """Log error message with optional exception and custom dimensions"""
    logger.logger.error(
        message, 
        extra={"custom_dimensions": kwargs} if kwargs else None,
        exc_info=error
    )

def log_warning(message: str, **kwargs):
    """Log warning message with optional custom dimensions"""
    logger.logger.warning(message, extra={"custom_dimensions": kwargs} if kwargs else None)

# Health check function
def health_check() -> Dict[str, Any]:
    """Return telemetry system health status"""
    return {
        "azure_logging_available": AZURE_LOGGING_AVAILABLE,
        "connection_string_configured": bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")),
        "metrics_exporter_active": logger.metrics_exporter is not None,
        "logger_level": logger.logger.level,
        "handlers_count": len(logger.logger.handlers)
    } 
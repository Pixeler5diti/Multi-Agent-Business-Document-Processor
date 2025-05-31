// Global variables
let allResults = [];
let filteredResults = [];
let statistics = {};

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

async function initializeApp() {
    // Set up event listeners
    setupEventListeners();
    
    // Load initial data
    await loadStatistics();
    await loadResults();
    
    // Set up periodic refresh
    setInterval(async () => {
        await loadStatistics();
        await loadResults();
    }, 30000); // Refresh every 30 seconds
}

function setupEventListeners() {
    // File upload form
    document.getElementById('uploadForm').addEventListener('submit', handleFileUpload);
    
    // Filter controls
    document.getElementById('statusFilter').addEventListener('change', applyFilters);
    document.getElementById('fileTypeFilter').addEventListener('change', applyFilters);
    document.getElementById('intentFilter').addEventListener('change', applyFilters);
    
    // File input change event
    document.getElementById('fileInput').addEventListener('change', function() {
        const file = this.files[0];
        if (file) {
            validateFile(file);
        }
    });
}

function validateFile(file) {
    const maxSize = 10 * 1024 * 1024; // 10MB
    const allowedTypes = [
        'application/pdf',
        'application/json',
        'text/plain',
        'message/rfc822',
        'application/vnd.ms-outlook'
    ];
    
    const fileExtension = file.name.toLowerCase().split('.').pop();
    const allowedExtensions = ['pdf', 'json', 'txt', 'eml', 'msg'];
    
    if (file.size > maxSize) {
        showToast('error', 'File too large. Maximum size is 10MB.');
        document.getElementById('fileInput').value = '';
        return false;
    }
    
    if (!allowedExtensions.includes(fileExtension)) {
        showToast('error', 'Invalid file type. Please upload PDF, JSON, or Email files.');
        document.getElementById('fileInput').value = '';
        return false;
    }
    
    return true;
}

async function handleFileUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) {
        showToast('error', 'Please select a file to upload.');
        return;
    }
    
    if (!validateFile(file)) {
        return;
    }
    
    const uploadBtn = document.getElementById('uploadBtn');
    const progressContainer = document.getElementById('uploadProgress');
    const progressBar = progressContainer.querySelector('.progress-bar');
    const progressText = document.getElementById('progressText');
    
    try {
        // Show progress
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
        progressContainer.style.display = 'block';
        progressBar.style.width = '10%';
        progressText.textContent = 'Uploading file...';
        
        // Create form data
        const formData = new FormData();
        formData.append('file', file);
        
        // Upload file
        progressBar.style.width = '30%';
        progressText.textContent = 'Classifying document...';
        
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        progressBar.style.width = '70%';
        progressText.textContent = 'Processing with agents...';
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        progressBar.style.width = '100%';
        progressText.textContent = 'Processing complete!';
        
        // Show success message
        showToast('success', `File "${file.name}" processed successfully!`);
        
        // Clear form
        fileInput.value = '';
        
        // Refresh data
        await loadResults();
        await loadStatistics();
        
        // Show result details
        setTimeout(() => {
            showResultDetails(result.processing_id);
        }, 1000);
        
    } catch (error) {
        console.error('Upload error:', error);
        showToast('error', `Upload failed: ${error.message}`);
        progressBar.style.width = '100%';
        progressBar.classList.remove('progress-bar-animated');
        progressBar.classList.add('bg-danger');
        progressText.textContent = 'Upload failed';
    } finally {
        // Reset UI
        setTimeout(() => {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="fas fa-upload me-2"></i>Process Document';
            progressContainer.style.display = 'none';
            progressBar.style.width = '0%';
            progressBar.classList.add('progress-bar-animated');
            progressBar.classList.remove('bg-danger');
        }, 2000);
    }
}

async function loadStatistics() {
    try {
        const response = await fetch('/results');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success && data.results) {
            statistics = calculateStatistics(data.results);
            updateStatisticsDisplay();
        }
    } catch (error) {
        console.error('Error loading statistics:', error);
        document.getElementById('statisticsContent').innerHTML = `
            <div class="text-center text-danger">
                <i class="fas fa-exclamation-triangle mb-2"></i>
                <p class="mb-0">Failed to load statistics</p>
            </div>
        `;
    }
}

function calculateStatistics(results) {
    const stats = {
        total: results.length,
        byStatus: {},
        byFileType: {},
        byIntent: {},
        recent24h: 0
    };
    
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    
    results.forEach(result => {
        // Status breakdown
        stats.byStatus[result.status] = (stats.byStatus[result.status] || 0) + 1;
        
        // File type breakdown
        stats.byFileType[result.file_type] = (stats.byFileType[result.file_type] || 0) + 1;
        
        // Intent breakdown
        stats.byIntent[result.business_intent] = (stats.byIntent[result.business_intent] || 0) + 1;
        
        // Recent activity
        if (result.created_at && new Date(result.created_at) > yesterday) {
            stats.recent24h++;
        }
    });
    
    return stats;
}

function updateStatisticsDisplay() {
    const container = document.getElementById('statisticsContent');
    
    container.innerHTML = `
        <div class="stat-item fade-in">
            <div class="stat-number">${statistics.total}</div>
            <div class="stat-label">Total Processed</div>
        </div>
        
        <div class="stat-item fade-in">
            <div class="stat-number">${statistics.recent24h}</div>
            <div class="stat-label">Last 24 Hours</div>
        </div>
        
        <div class="stat-item fade-in">
            <div class="stat-number">${statistics.byStatus.completed || 0}</div>
            <div class="stat-label">Completed</div>
        </div>
        
        <div class="stat-item fade-in">
            <div class="stat-number">${Object.keys(statistics.byFileType).length}</div>
            <div class="stat-label">File Types</div>
        </div>
        
        <div class="mt-3">
            <h6 class="text-muted mb-2">File Types</h6>
            ${Object.entries(statistics.byFileType).map(([type, count]) => 
                `<div class="d-flex justify-content-between mb-1">
                    <span class="text-capitalize">${type}</span>
                    <span class="fw-bold">${count}</span>
                </div>`
            ).join('')}
        </div>
        
        <div class="mt-3">
            <h6 class="text-muted mb-2">Business Intents</h6>
            ${Object.entries(statistics.byIntent).map(([intent, count]) => 
                `<div class="d-flex justify-content-between mb-1">
                    <span>${intent}</span>
                    <span class="fw-bold">${count}</span>
                </div>`
            ).join('')}
        </div>
    `;
}

async function loadResults() {
    try {
        const response = await fetch('/results');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (data.success) {
            allResults = data.results || [];
            applyFilters();
        } else {
            throw new Error('Failed to load results');
        }
    } catch (error) {
        console.error('Error loading results:', error);
        document.getElementById('resultsContent').innerHTML = `
            <div class="text-center p-4 text-danger">
                <i class="fas fa-exclamation-triangle mb-2 fa-2x"></i>
                <p class="mb-0">Failed to load results</p>
                <button class="btn btn-outline-danger btn-sm mt-2" onclick="loadResults()">
                    <i class="fas fa-retry me-1"></i>Retry
                </button>
            </div>
        `;
    }
}

function applyFilters() {
    const statusFilter = document.getElementById('statusFilter').value;
    const fileTypeFilter = document.getElementById('fileTypeFilter').value;
    const intentFilter = document.getElementById('intentFilter').value;
    
    filteredResults = allResults.filter(result => {
        if (statusFilter && result.status !== statusFilter) return false;
        if (fileTypeFilter && result.file_type !== fileTypeFilter) return false;
        if (intentFilter && result.business_intent !== intentFilter) return false;
        return true;
    });
    
    updateResultsDisplay();
}

function updateResultsDisplay() {
    const container = document.getElementById('resultsContent');
    const countBadge = document.getElementById('resultsCount');
    
    countBadge.textContent = `${filteredResults.length} result${filteredResults.length !== 1 ? 's' : ''}`;
    
    if (filteredResults.length === 0) {
        container.innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-inbox fa-3x text-muted mb-3"></i>
                <h5 class="text-muted">No results found</h5>
                <p class="text-muted mb-0">Try adjusting your filters or upload a new document.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = filteredResults.map(result => createResultItem(result)).join('');
}

function createResultItem(result) {
    const statusBadgeClass = {
        'completed': 'badge-status-completed',
        'processing': 'badge-status-processing',
        'failed': 'badge-status-failed'
    }[result.status] || 'bg-secondary';
    
    const fileTypeIcon = {
        'pdf': 'fa-file-pdf text-danger',
        'json': 'fa-file-code text-info',
        'email': 'fa-envelope text-primary'
    }[result.file_type] || 'fa-file';
    
    const flags = result.metadata?.flags || result.flags || [];
    const actions = result.actions_taken || [];
    
    return `
        <div class="result-item slide-in" onclick="showResultDetails(${result.id})">
            <div class="result-header">
                <h6 class="result-filename">
                    <i class="fas ${fileTypeIcon} me-2"></i>
                    ${escapeHtml(result.filename)}
                </h6>
                <small class="text-muted">${formatDate(result.created_at)}</small>
            </div>
            
            <div class="result-meta">
                <span class="badge badge-file-type">${result.file_type.toUpperCase()}</span>
                <span class="badge badge-intent">${result.business_intent}</span>
                <span class="badge ${statusBadgeClass}">${result.status.toUpperCase()}</span>
                ${getConfidenceBadge(result)}
            </div>
            
            ${flags.length > 0 ? `
                <div class="mb-2">
                    ${flags.map(flag => `<span class="flag-item ${getFlagClass(flag)}">${flag}</span>`).join('')}
                </div>
            ` : ''}
            
            ${actions.length > 0 ? `
                <div class="mb-2">
                    <small class="text-muted d-block mb-1">Actions:</small>
                    ${actions.map(action => `<span class="action-item">${action}</span>`).join('')}
                </div>
            ` : ''}
            
            <p class="result-summary">
                ${getResultSummary(result)}
            </p>
        </div>
    `;
}

function getFlagClass(flag) {
    if (flag.includes('URGENT')) return 'flag-urgent';
    if (flag.includes('HIGH_VALUE')) return 'flag-high-value';
    if (flag.includes('REGULATORY') || flag.includes('GDPR') || flag.includes('FDA')) return 'flag-regulatory';
    return '';
}

function getConfidenceBadge(result) {
    const confidence = result.metadata?.confidence || 0;
    const percentage = Math.round(confidence * 100);
    
    let badgeClass = 'bg-secondary';
    if (percentage >= 80) badgeClass = 'bg-success';
    else if (percentage >= 60) badgeClass = 'bg-warning';
    else if (percentage >= 40) badgeClass = 'bg-info';
    else badgeClass = 'bg-danger';
    
    return `<span class="badge ${badgeClass}">Confidence: ${percentage}%</span>`;
}

function getResultSummary(result) {
    const extractedData = result.extracted_data || {};
    
    if (result.file_type === 'email') {
        const sender = extractedData.sender || 'Unknown sender';
        const urgency = extractedData.urgency || 'normal';
        const tone = extractedData.tone || 'neutral';
        return `From: ${escapeHtml(sender)} | Urgency: ${urgency} | Tone: ${tone}`;
    } else if (result.file_type === 'json') {
        const fieldCount = extractedData.field_count || 0;
        const amount = extractedData.monetary_value;
        return `${fieldCount} fields${amount ? ` | Amount: ${amount}` : ''}`;
    } else if (result.file_type === 'pdf') {
        const pageCount = extractedData.page_count || 0;
        const amount = extractedData.total_amount;
        return `${pageCount} pages${amount ? ` | Amount: $${amount}` : ''}`;
    }
    
    return 'Processed successfully';
}

async function showResultDetails(processingId) {
    try {
        const response = await fetch(`/results/${processingId}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error('Failed to load result details');
        }
        
        const result = data.result;
        updateResultModal(result);
        
        const modal = new bootstrap.Modal(document.getElementById('resultModal'));
        modal.show();
        
    } catch (error) {
        console.error('Error loading result details:', error);
        showToast('error', 'Failed to load result details');
    }
}

function updateResultModal(result) {
    const modalContent = document.getElementById('resultModalContent');
    
    modalContent.innerHTML = `
        <div class="row">
            <div class="col-md-6">
                <h6 class="fw-bold mb-3">Basic Information</h6>
                <table class="table table-sm">
                    <tr>
                        <td class="fw-bold">Filename:</td>
                        <td>${escapeHtml(result.filename)}</td>
                    </tr>
                    <tr>
                        <td class="fw-bold">File Type:</td>
                        <td><span class="badge badge-file-type">${result.file_type.toUpperCase()}</span></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Business Intent:</td>
                        <td><span class="badge badge-intent">${result.business_intent}</span></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Status:</td>
                        <td><span class="badge badge-status-${result.status}">${result.status.toUpperCase()}</span></td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Confidence:</td>
                        <td>${getConfidenceBadge(result)}</td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Created:</td>
                        <td>${formatDate(result.created_at)}</td>
                    </tr>
                    <tr>
                        <td class="fw-bold">Updated:</td>
                        <td>${formatDate(result.updated_at)}</td>
                    </tr>
                </table>
            </div>
            
            <div class="col-md-6">
                <h6 class="fw-bold mb-3">Quick Summary</h6>
                <div class="mb-3">
                    <strong>Key Findings:</strong>
                    <ul class="mt-2">
                        ${getProcessingSummaryList(result)}
                    </ul>
                </div>
                
                ${result.actions_taken && result.actions_taken.length > 0 ? `
                    <div class="mb-3">
                        <strong>Actions Taken:</strong>
                        <div class="mt-2">
                            ${result.actions_taken.map(action => `<span class="action-item">${action}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        </div>
        
        <!-- Agent Processing Trace -->
        <div class="row mt-4">
            <div class="col-12">
                <h6 class="fw-bold mb-3">Agent Processing Trace</h6>
                <div class="accordion" id="agentTrace">
                    ${generateAgentTraceAccordion(result)}
                </div>
            </div>
        </div>
    `;
}

function getProcessingSummaryList(result) {
    const items = [];
    const metadata = result.metadata || {};
    const extracted = result.extracted_data || {};
    
    // Classification info
    if (metadata.reasoning) {
        items.push(`<li>Classification: ${metadata.reasoning}</li>`);
    }
    
    // File type specific info
    if (result.file_type === 'email') {
        if (extracted.sender) items.push(`<li>Sender: ${escapeHtml(extracted.sender)}</li>`);
        if (extracted.urgency) items.push(`<li>Urgency: ${extracted.urgency}</li>`);
        if (extracted.tone) items.push(`<li>Tone: ${extracted.tone}</li>`);
    } else if (result.file_type === 'pdf') {
        if (extracted.page_count) items.push(`<li>Pages: ${extracted.page_count}</li>`);
        if (extracted.total_amount) items.push(`<li>Amount: $${extracted.total_amount}</li>`);
    } else if (result.file_type === 'json') {
        if (extracted.field_count) items.push(`<li>Fields: ${extracted.field_count}</li>`);
        if (extracted.monetary_value) items.push(`<li>Value: ${extracted.monetary_value}</li>`);
    }
    
    return items.length > 0 ? items.join('') : '<li>No specific details extracted</li>';
}

function generateAgentTraceAccordion(result) {
    const stages = [
        {
            id: 'classifier',
            title: 'Stage 1: Document Classification',
            icon: 'fa-search',
            content: generateClassifierTrace(result)
        },
        {
            id: 'agent',
            title: `Stage 2: ${result.file_type.toUpperCase()} Agent Processing`,
            icon: 'fa-cogs',
            content: generateAgentTrace(result)
        },
        {
            id: 'actions',
            title: 'Stage 3: Action Router & Triggers',
            icon: 'fa-route',
            content: generateActionTrace(result)
        }
    ];
    
    return stages.map((stage, index) => `
        <div class="accordion-item">
            <h2 class="accordion-header" id="heading${stage.id}">
                <button class="accordion-button ${index === 0 ? '' : 'collapsed'}" type="button" 
                        data-bs-toggle="collapse" data-bs-target="#collapse${stage.id}" 
                        aria-expanded="${index === 0 ? 'true' : 'false'}" aria-controls="collapse${stage.id}">
                    <i class="fas ${stage.icon} me-2"></i>
                    ${stage.title}
                </button>
            </h2>
            <div id="collapse${stage.id}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" 
                 aria-labelledby="heading${stage.id}" data-bs-parent="#agentTrace">
                <div class="accordion-body">
                    ${stage.content}
                </div>
            </div>
        </div>
    `).join('');
}

function generateClassifierTrace(result) {
    const metadata = result.metadata || {};
    const confidence = metadata.confidence || 0;
    const reasoning = metadata.reasoning || 'No reasoning provided';
    
    return `
        <div class="trace-section">
            <h6 class="text-primary">Classification Results</h6>
            <div class="row">
                <div class="col-md-6">
                    <strong>File Type:</strong> ${result.file_type}<br>
                    <strong>Business Intent:</strong> ${result.business_intent}<br>
                    <strong>Confidence:</strong> ${Math.round(confidence * 100)}%<br>
                    <strong>Method:</strong> ${metadata.reasoning ? 'Rule-based analysis' : 'AI classification'}
                </div>
                <div class="col-md-6">
                    <strong>Reasoning:</strong><br>
                    <em>${reasoning}</em>
                </div>
            </div>
            <div class="mt-3">
                <strong>Timestamp:</strong> ${formatDate(result.created_at)}
                <span class="badge bg-success ms-2">✓ Completed</span>
            </div>
        </div>
    `;
}

function generateAgentTrace(result) {
    const extracted = result.extracted_data || {};
    const metadata = result.metadata || {};
    const processingAgent = metadata.processing_agent || `${result.file_type}_agent`;
    
    let agentSpecificInfo = '';
    
    if (result.file_type === 'email') {
        agentSpecificInfo = `
            <div class="row">
                <div class="col-md-6">
                    <strong>Email Analysis:</strong><br>
                    • Sender: ${extracted.sender || 'Not detected'}<br>
                    • Urgency: ${extracted.urgency || 'Normal'}<br>
                    • Tone: ${extracted.tone || 'Neutral'}<br>
                    • Sentiment: ${extracted.sentiment || 'Neutral'}
                </div>
                <div class="col-md-6">
                    <strong>Extracted Info:</strong><br>
                    • Content Length: ${extracted.content_length || 0} chars<br>
                    • Has Attachments: ${extracted.has_attachments ? 'Yes' : 'No'}<br>
                    • Contact Info: ${extracted.contact_info || 'None found'}
                </div>
            </div>
        `;
    } else if (result.file_type === 'pdf') {
        agentSpecificInfo = `
            <div class="row">
                <div class="col-md-6">
                    <strong>PDF Analysis:</strong><br>
                    • Pages: ${extracted.page_count || 0}<br>
                    • Text Length: ${extracted.text_length || 0} chars<br>
                    • Total Amount: ${extracted.total_amount ? '$' + extracted.total_amount : 'None'}
                </div>
                <div class="col-md-6">
                    <strong>Business Fields:</strong><br>
                    • Invoice Number: ${extracted.invoice_number || 'Not found'}<br>
                    • Phone: ${extracted.phone_number || 'Not found'}<br>
                    • Compliance: ${extracted.compliance_mentions ? extracted.compliance_mentions.join(', ') : 'None'}
                </div>
            </div>
        `;
    } else if (result.file_type === 'json') {
        agentSpecificInfo = `
            <div class="row">
                <div class="col-md-6">
                    <strong>JSON Analysis:</strong><br>
                    • Field Count: ${extracted.field_count || 0}<br>
                    • Document ID: ${extracted.document_id || 'Not found'}<br>
                    • Monetary Value: ${extracted.monetary_value || 'None'}
                </div>
                <div class="col-md-6">
                    <strong>Validation:</strong><br>
                    • Schema Valid: ${metadata.validation_result?.is_valid ? 'Yes' : 'No'}<br>
                    • Warnings: ${metadata.validation_result?.warnings?.length || 0}<br>
                    • Data Quality: ${metadata.validation_result?.warnings?.length > 0 ? 'Issues Found' : 'Good'}
                </div>
            </div>
        `;
    }
    
    return `
        <div class="trace-section">
            <h6 class="text-info">Agent Processing</h6>
            <strong>Processing Agent:</strong> ${processingAgent}<br>
            ${agentSpecificInfo}
            <div class="mt-3">
                <strong>Timestamp:</strong> ${formatDate(result.updated_at)}
                <span class="badge bg-success ms-2">✓ Completed</span>
            </div>
        </div>
    `;
}

function generateActionTrace(result) {
    const actions = result.actions_taken || [];
    const hasActions = actions.length > 0;
    
    const actionDetails = actions.map(action => {
        let description = '';
        
        switch(action) {
            case 'crm_escalation':
                description = 'Escalated to CRM system due to complaint with urgent/angry tone';
                break;
            case 'risk_alert':
                description = 'Risk alert triggered for potential fraud or high-value transaction';
                break;
            case 'high_value_invoice_approval':
                description = 'High-value invoice flagged for approval workflow';
                break;
            case 'rfq_sales_notification':
                description = 'Sales team notified of new RFQ submission';
                break;
            case 'compliance_team_alert':
                description = 'Compliance team alerted of regulatory content';
                break;
            default:
                description = `Custom action: ${action}`;
        }
        
        return `
            <div class="action-trace-item mb-2 p-2 border rounded">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${action}</strong><br>
                        <small class="text-muted">${description}</small>
                    </div>
                    <div>
                        <span class="badge bg-success">✓ Executed</span>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="retryAction('${action}', ${result.id})">
                            <i class="fas fa-redo"></i> Retry
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    return `
        <div class="trace-section">
            <h6 class="text-warning">Action Router Results</h6>
            ${hasActions ? `
                <p><strong>Actions Triggered:</strong> ${actions.length}</p>
                ${actionDetails}
            ` : `
                <p>No automated actions were triggered for this document.</p>
                <div class="alert alert-info">
                    <small>Actions are triggered based on document content, urgency, tone, and business rules.</small>
                </div>
            `}
            <div class="mt-3">
                <strong>Timestamp:</strong> ${formatDate(result.updated_at)}
                <span class="badge ${hasActions ? 'bg-success' : 'bg-secondary'} ms-2">
                    ${hasActions ? '✓ Actions Executed' : '• No Actions Required'}
                </span>
            </div>
        </div>
    `;
}

async function retryAction(actionType, processingId) {
    try {
        showToast('info', `Retrying action: ${actionType}...`);
        
        const response = await fetch('/retry-action', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                processing_id: processingId,
                action_type: actionType
            })
        });
        
        if (response.ok) {
            showToast('success', `Action ${actionType} retried successfully`);
            await showResultDetails(processingId);
        } else {
            showToast('error', `Failed to retry action: ${actionType}`);
        }
    } catch (error) {
        console.error('Error retrying action:', error);
        showToast('error', 'Error retrying action');
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    // Less than 1 minute
    if (diff < 60000) {
        return 'Just now';
    }
    
    // Less than 1 hour
    if (diff < 3600000) {
        const minutes = Math.floor(diff / 60000);
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ago`;
    }
    
    // Less than 1 day
    if (diff < 86400000) {
        const hours = Math.floor(diff / 3600000);
        return `${hours} hour${hours !== 1 ? 's' : ''} ago`;
    }
    
    // Older than 1 day
    return date.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(type, message) {
    const toastElement = document.getElementById(`${type}Toast`);
    const toastBody = document.getElementById(`${type}ToastBody`);
    
    toastBody.textContent = message;
    
    const toast = new bootstrap.Toast(toastElement, {
        autohide: true,
        delay: type === 'error' ? 5000 : 3000
    });
    
    toast.show();
}

async function refreshData() {
    const refreshBtn = document.querySelector('[onclick="refreshData()"]');
    const originalContent = refreshBtn.innerHTML;
    
    refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
    refreshBtn.disabled = true;
    
    try {
        await Promise.all([
            loadStatistics(),
            loadResults()
        ]);
        
        showToast('success', 'Data refreshed successfully');
    } catch (error) {
        showToast('error', 'Failed to refresh data');
    } finally {
        refreshBtn.innerHTML = originalContent;
        refreshBtn.disabled = false;
    }
}

// Global error handler
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    showToast('error', 'An unexpected error occurred');
});

// Handle network errors
window.addEventListener('online', function() {
    showToast('success', 'Connection restored');
    refreshData();
});

window.addEventListener('offline', function() {
    showToast('error', 'Connection lost');
});

// AllFind shared multi-tenant SaaS stack
// deploy with: az deployment group create -g <rg> -f allfind.bicep -p envName=<dev|stage|prod>

@description('Environment tag (dev,stage,prod)')
param envName string = 'dev'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('SKU for Azure AI Search (basic, standard, standard3)')
param searchSku string = 'standard'

@description('Function App SKU (Y1 for consumption, EP1 for premium)')
param funcSku string = 'Y1'

@description('Static Web App SKU (Free or Standard)')
param staticSku string = 'Free'

@secure()
@description('Azure OpenAI API Key')
param openAiApiKey string

@secure()
@description('Azure OpenAI Endpoint')
param openAiEndpoint string

@secure()
@description('Microsoft Graph Client ID')
param graphClientId string

@secure()
@description('Microsoft Graph Client Secret')
param graphClientSecret string

@secure()
@description('Azure AD Tenant ID')
param tenantId string

@description('Admin email for alerts')
param adminEmail string = 'admin@yourdomain.com'

// Generate unique suffix to avoid global-name clashes
var suffix = uniqueString(resourceGroup().id, envName)
var stgName = 'allfindst${suffix}'
var funcName = 'allfindfunc${suffix}'
var apiName = 'allfindapi${suffix}'
var swebName = 'allfindswa${suffix}'
var kvName = 'allfindkv${suffix}'
var searchName = 'allfindsearch${suffix}'
var serviceBusName = 'allfindsb${suffix}'

// ---------------- Storage for Functions & queue ----------------
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: stgName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

// ---------------- Service Bus for large file processing ----------------
resource serviceBus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: serviceBusName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {}
}

resource largeFileQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBus
  name: 'large-file-processing'
  properties: {
    maxDeliveryCount: 3
    lockDuration: 'PT5M'
    defaultMessageTimeToLive: 'P1D'
    deadLetteringOnMessageExpiration: true
  }
}

// ---------------- Function plan & app (webhooks, renewal, poll) ---------------
resource funcPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'allfind-func-plan-${suffix}'
  location: location
  sku: {
    name: funcSku
    tier: funcSku == 'Y1' ? 'Dynamic' : 'ElasticPremium'
  }
  kind: 'functionapp'
  properties: {
    reserved: true // Linux
  }
}

// Separate plan for API (web apps can't use consumption plan)
resource apiPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'allfind-api-plan-${suffix}'
  location: location
  sku: {
    name: 'B1'  // Basic plan for API
    tier: 'Basic'
  }
  kind: 'app'
  properties: {
    reserved: true // Linux
  }
}

resource funcApp 'Microsoft.Web/sites@2022-09-01' = {
  name: funcName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: funcPlan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=core.windows.net' }
        { name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING', value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${storage.listKeys().keys[0].value};EndpointSuffix=core.windows.net' }
        { name: 'WEBSITE_CONTENTSHARE', value: toLower(funcName) }
        
        // AllFind specific settings
        { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${searchName}.search.windows.net' }
        { name: 'AZURE_SEARCH_INDEX_NAME', value: 'allfind-index' }
        { name: 'AZURE_SEARCH_KEY', value: search.listAdminKeys().primaryKey }
        { name: 'AZURE_OPENAI_API_KEY', value: openAiApiKey }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_CLIENT_ID', value: graphClientId }
        { name: 'AZURE_CLIENT_SECRET', value: graphClientSecret }
        { name: 'AZURE_TENANT_ID', value: tenantId }
        
        // Service Bus for large files
        { name: 'SERVICE_BUS_CONNECTION_STRING', value: listKeys('${serviceBus.id}/AuthorizationRules/RootManageSharedAccessKey', serviceBus.apiVersion).primaryConnectionString }
        
        // Webhook configuration
        { name: 'WEBHOOK_CLIENT_STATE', value: 'allfind-webhook-secret-${suffix}' }
        
        // Performance settings (ChatGPT recommendations)
        { name: 'FUNCTIONS_WORKER_PROCESS_COUNT', value: funcSku == 'Y1' ? '1' : '2' }
        { name: 'WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT', value: '10' }
        
        // Application Insights (ChatGPT monitoring recommendations)
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
      ]
    }
  }
  identity: {
    type: 'SystemAssigned'
  }

}

// ---------------- FastAPI back-end --------------------
resource apiSite 'Microsoft.Web/sites@2022-09-01' = {
  name: apiName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: apiPlan.id // Use dedicated API plan
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        { name: 'WEBSITES_PORT', value: '8000' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        
        // AllFind API settings
        { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://${searchName}.search.windows.net' }
        { name: 'AZURE_SEARCH_INDEX_NAME', value: 'allfind-index' }
        { name: 'AZURE_SEARCH_KEY', value: search.listAdminKeys().primaryKey }
        { name: 'AZURE_OPENAI_API_KEY', value: openAiApiKey }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_CLIENT_ID', value: graphClientId }
        { name: 'AZURE_CLIENT_SECRET', value: graphClientSecret }
        { name: 'AZURE_TENANT_ID', value: tenantId }
        
        // Application Insights for API
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
      ]
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// ---------------- Static Web App (React SPA) ------------------
resource swa 'Microsoft.Web/staticSites@2022-03-01' = {
  name: swebName
  location: location
  sku: {
    name: staticSku
  }
  properties: {
    repositoryUrl: '' // manual upload okay
    buildProperties: {
      appLocation: '/allfind-frontend'
      outputLocation: 'build'
      appBuildCommand: 'npm run build'
    }
    stagingEnvironmentPolicy: 'Enabled'
  }
}

// ---------------- Azure AI Search -------------------
resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchName
  location: location
  sku: {
    name: searchSku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
    networkRuleSet: {
      ipRules: []
    }
    encryptionWithCmk: {
      enforcement: 'Unspecified'
    }
    disableLocalAuth: false
    authOptions: {
      apiKeyOnly: {}
    }
  }
}

// ---------------- Application Insights & Log Analytics -----------------
resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-${suffix}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      searchVersion: 1
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'ai-${suffix}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logWorkspace.id
  }
}

// Search service diagnostics
resource searchDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'search-diag'
  scope: search
  properties: {
    workspaceId: logWorkspace.id
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

// Service Bus diagnostics
resource serviceBusDiag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'servicebus-diag'
  scope: serviceBus
  properties: {
    workspaceId: logWorkspace.id
    logs: [
      { category: 'OperationalLogs', enabled: true }
    ]
    metrics: [
      { category: 'AllMetrics', enabled: true }
    ]
  }
}

// Action Group for alerts
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'allfind-alerts-${suffix}'
  location: 'Global'
  properties: {
    groupShortName: 'AllFind'
    enabled: true
    emailReceivers: [
      {
        name: 'Admin'
        emailAddress: adminEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// Alert Rules
resource webhookFailAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'webhook-fail-alert-${suffix}'
  location: location
  properties: {
    description: 'Webhook failures detected in last 15 minutes'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where cloud_RoleName contains "allfind"
            | where name contains "webhook"
            | where success == false
            | summarize count()
          '''
          timeAggregation: 'Count'
          threshold: 0
          operator: 'GreaterThan'
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
    scopes: [appInsights.id]
  }
}

resource indexingSlowAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'indexing-slow-alert-${suffix}'
  location: location
  properties: {
    description: 'Average indexing time > 8 seconds'
    enabled: true
    severity: 3
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    criteria: {
      allOf: [
        {
          query: '''
            customMetrics
            | where name == "IndexingDurationMs"
            | summarize avg_ms = avg(todouble(value))
            | where avg_ms > 8000
          '''
          timeAggregation: 'Count'
          threshold: 0
          operator: 'GreaterThan'
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
    scopes: [appInsights.id]
  }
}

resource queueBacklogAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'queue-backlog-alert-${suffix}'
  location: location
  properties: {
    description: 'Service Bus queue backlog > 500 messages'
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT10M'
    criteria: {
      allOf: [
        {
          query: '''
            AzureMetrics
            | where ResourceProvider == "MICROSOFT.SERVICEBUS"
            | where MetricName == "ActiveMessages"
            | summarize max_backlog = max(todouble(Average))
            | where max_backlog > 500
          '''
          timeAggregation: 'Count'
          threshold: 0
          operator: 'GreaterThan'
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
    scopes: [logWorkspace.id]
  }
}

resource searchThrottleAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'search-throttle-alert-${suffix}'
  location: location
  properties: {
    description: 'Search service throttling detected'
    enabled: true
    severity: 1
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: '''
            AzureMetrics
            | where ResourceProvider == "MICROSOFT.SEARCH"
            | where MetricName == "ThrottledSearchQueriesPercentage"
            | where Average > 10
            | summarize count()
          '''
          timeAggregation: 'Count'
          threshold: 0
          operator: 'GreaterThan'
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
    scopes: [logWorkspace.id]
  }
}

// ---------------- Key Vault for secrets -----------------
resource kv 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    sku: {
      family: 'A'
      name: 'standard'
    }
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: funcApp.identity.principalId
        permissions: {
          secrets: ['get', 'list']
        }
      }
      {
        tenantId: subscription().tenantId
        objectId: apiSite.identity.principalId
        permissions: {
          secrets: ['get', 'list']
        }
      }
    ]
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}

// Store secrets in Key Vault
resource kvSecretOpenAI 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: kv
  name: 'azure-openai-api-key'
  properties: {
    value: openAiApiKey
  }
}

resource kvSecretGraphSecret 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: kv
  name: 'graph-client-secret'
  properties: {
    value: graphClientSecret
  }
}

resource kvSecretSearchKey 'Microsoft.KeyVault/vaults/secrets@2023-02-01' = {
  parent: kv
  name: 'azure-search-key'
  properties: {
    value: search.listAdminKeys().primaryKey
  }
}

// ---------------- RBAC for managed identities ----------------
// Grant Function App access to Search Service
resource funcSearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, funcApp.id, 'Search Index Data Contributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '8ebe5a00-799e-43f5-93ac-243d3dce84a7') // Search Index Data Contributor
    principalId: funcApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Grant API Site access to Search Service
resource apiSearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, apiSite.id, 'Search Index Data Reader')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f') // Search Index Data Reader
    principalId: apiSite.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// ---------------- Outputs ----------------------------
output functionEndpoint string = 'https://${funcApp.name}.azurewebsites.net'
output apiEndpoint string = 'https://${apiSite.name}.azurewebsites.net'
output spaUrl string = 'https://${swa.properties.defaultHostname}'
output searchEndpoint string = 'https://${search.name}.search.windows.net'
output keyVaultName string = kv.name
output serviceBusEndpoint string = serviceBus.properties.serviceBusEndpoint
output webhookUrl string = 'https://${funcApp.name}.azurewebsites.net/api/webhook_handler'
output appInsightsName string = appInsights.name
output logWorkspaceName string = logWorkspace.name

// Deployment summary
output deploymentSummary object = {
  environment: envName
  resourceGroup: resourceGroup().name
  functionApp: funcApp.name
  apiSite: apiSite.name
  staticWebApp: swa.name
  searchService: search.name
  keyVault: kv.name
  serviceBus: serviceBus.name
  storageAccount: storage.name
} 
// AllFind shared multi-tenant SaaS stack
// deploy with: az deployment group create -g <rg> -f allfind.bicep -p envName=<dev|stage|prod>

@description('Environment name (e.g., prod, dev)')
param envName string = 'prod'

@description('Location for all resources')
param location string = 'canadaeast'

@description('Unique suffix for resource names')
param uniqueSuffix string = uniqueString(resourceGroup().id)

// AllFind branded resource names
var allFindPrefix = 'allfind'
var staticWebAppName = '${allFindPrefix}-app-${envName}'
var apiAppName = '${allFindPrefix}-api-${envName}'
var functionAppName = '${allFindPrefix}-func-${envName}'
var searchServiceName = '${allFindPrefix}-search-${envName}'
var storageAccountName = '${allFindPrefix}st${uniqueSuffix}'
var keyVaultName = '${allFindPrefix}-kv-${envName}'
var serviceBusName = '${allFindPrefix}-sb-${envName}'
var logAnalyticsName = '${allFindPrefix}-logs-${envName}'
var appInsightsName = '${allFindPrefix}-ai-${envName}'

// App Service Plans
var apiAppServicePlanName = '${allFindPrefix}-api-plan-${envName}'
var funcAppServicePlanName = '${allFindPrefix}-func-plan-${envName}'

// Existing resources (keep references)
@description('Existing Azure OpenAI service name')
param existingOpenAIName string = 'docusense-azure-open-ai'

@description('Existing Azure OpenAI resource group')
param existingOpenAIResourceGroup string = resourceGroup().name

// Reference existing Azure OpenAI
resource existingOpenAI 'Microsoft.CognitiveServices/accounts@2023-05-01' existing = {
  name: existingOpenAIName
  scope: resourceGroup(existingOpenAIResourceGroup)
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// Azure AI Search
resource searchService 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'standard'
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
  }
}

// Service Bus Namespace
resource serviceBus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: serviceBusName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
}

// Service Bus Queue for large files
resource largeFileQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: serviceBus
  name: 'large-files'
  properties: {
    maxSizeInMegabytes: 1024
    defaultMessageTimeToLive: 'P1D'
  }
}

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    accessPolicies: []
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// Static Web App (Frontend)
resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: staticWebAppName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    repositoryUrl: 'https://github.com/Antoine-CL/allfind'
    branch: 'main'
    buildProperties: {
      appLocation: 'docusense-frontend'
      outputLocation: 'build'
    }
  }
}

// API App Service Plan
resource apiAppServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: apiAppServicePlanName
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
  kind: 'linux'
}

// API App Service
resource apiAppService 'Microsoft.Web/sites@2023-01-01' = {
  name: apiAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: apiAppServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: existingOpenAI.properties.endpoint
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${searchService.name}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_KEY'
          value: searchService.listAdminKeys().primaryKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'AZURE_STORAGE_CONNECTION_STRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'SERVICE_BUS_CONNECTION_STRING'
          value: listKeys('${serviceBus.id}/AuthorizationRules/RootManageSharedAccessKey', serviceBus.apiVersion).primaryConnectionString
        }
      ]
    }
  }
}

// Function App Service Plan
resource funcAppServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: funcAppServicePlanName
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
  kind: 'functionapp,linux'
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: funcAppServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${storageAccount.listKeys().keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsights.properties.ConnectionString
        }
        {
          name: 'AZURE_SEARCH_ENDPOINT'
          value: 'https://${searchService.name}.search.windows.net'
        }
        {
          name: 'AZURE_SEARCH_KEY'
          value: searchService.listAdminKeys().primaryKey
        }
      ]
    }
  }
}

// Alert Action Group
resource alertActionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${allFindPrefix}-alerts-${envName}'
  location: 'global'
  properties: {
    groupShortName: 'AllFind'
    enabled: true
    emailReceivers: []
  }
}

// Monitoring Alerts
resource webhookFailAlert 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'allfind-webhook-failures'
  location: location
  properties: {
    displayName: 'AllFind Webhook Failures'
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [appInsights.id]
    criteria: {
      allOf: [
        {
          query: 'requests | where url contains "webhook" and toint(resultCode) >= 400'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 5
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [alertActionGroup.id]
    }
  }
}

// Outputs
output staticWebAppUrl string = 'https://${staticWebApp.properties.defaultHostname}'
output apiUrl string = 'https://${apiAppService.properties.defaultHostName}'
output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output searchServiceUrl string = 'https://${searchService.name}.search.windows.net'
output staticWebAppName string = staticWebApp.name
output apiAppName string = apiAppService.name
output functionAppName string = functionApp.name

// Deployment summary
output deploymentSummary object = {
  environment: envName
  resourceGroup: resourceGroup().name
  functionApp: functionApp.name
  apiSite: apiAppService.name
  staticWebApp: staticWebApp.name
  searchService: searchService.name
  keyVault: keyVault.name
  serviceBus: serviceBus.name
  storageAccount: storageAccount.name
} 
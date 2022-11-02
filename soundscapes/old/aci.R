args = commandArgs(TRUE)
suppressMessages(suppressWarnings(library(seewave)))
suppressMessages(suppressWarnings(library(tuneR)))
archivo<- readWave(args[1])
AmplPeaks = c()
if(length(archivo@left)>archivo@samp.rate)# at least one second of audio
{
    value = FALSE
    tryCatch(
        {
            value = ACI(archivo)
        }
        ,
        error = function(e)
        {
            cat ('err1')
            quit()
        }
    );
    
    if(!value)
    {
        cat('err2')
    }
    else
    {
        cat(value)
    }
    
}else cat ('err3')


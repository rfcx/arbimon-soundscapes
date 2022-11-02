

args = commandArgs(TRUE)

library(methods)
suppressMessages(suppressWarnings(library(seewave)))
suppressMessages(suppressWarnings(library(tuneR)))

work_fpeaks = function(filename, threshold, bin.size, frequency, norm.channel=T, norm.meanspec = F){
    archivo = FALSE

    tryCatch({
        archivo <- readWave(filename)
    },
    error = function(e){
        return('err0')
        quit()
    });
    
    AmplPeaks = c()
    
    if(class(archivo) == 'Wave' || class(archivo) == 'WaveMC'){
        data = c()
        
        if(class(archivo) == 'Wave'){
            data = archivo@left
        } else {
            data = archivo@.Data
        }
        
        if(archivo@pcm){
            channel.max = 2**(archivo@bit - 1)
        } else {
            channel.max = 1.0
        }
        
        if(norm.channel){
            data <- data / channel.max
            if(class(archivo) == 'Wave'){
                archivo@left <- data
            } else {
                archivo@.Data <- data
            }
        }
        
        if(length(data)>archivo@samp.rate){ # at least one second of audio
            bin_size = as.numeric(bin.size)
            picos = c()
            spec = c()
            srate = archivo@samp.rate
            n = floor((srate)/bin_size) # search for the next power of two
            n = n - 1
            n = bitwOr(n,bitwShiftR(n, 1) )
            n = bitwOr(n,bitwShiftR(n, 2)  )
            n = bitwOr(n,bitwShiftR(n, 4) )
            n = bitwOr(n,bitwShiftR(n, 8) )
            n = bitwOr(n,bitwShiftR(n, 16) )
            windowsize = n + 1
            
            tryCatch({
                spec <- meanspec(archivo, f=srate, plot=FALSE,wl=windowsize, norm=norm.meanspec)
            },
            error = function(e){
                return('err1')
                quit()
            });
            
            epsilonValue = 0.00001
            if(as.numeric(threshold) > 0.00001){
                epsilonValue = as.numeric(threshold)
            }
             
            tryCatch({
                #,amp=c(0.01,0.01)
                picos<-fpeaks(spec,freq=as.numeric(frequency),plot=FALSE,threshold=epsilonValue)
            },
            error = function(e){
                return('err2')
                quit()
            });
            
            if(is.null(picos)){
                return('[]')
            }
            
            if( is.na(picos) || length(picos[,1]) < 1){
               return('[]')
            } else {
                picos[is.na(picos)]<-0
                p<-dim(picos)
                retStr = ''

                if (p[1]>=1){

                    pico<-data.frame(picos)
                    retStr = paste( "{\"f\":", pico[1,1], ",\"a\":" ,pico[1,2]   , "}" ,sep="" )
                    ii = 2

                    while(ii <=length(pico[,1])){
                        retStr =paste(retStr, paste( "{\"f\":", pico[ii,1], ",\"a\":" ,pico[ii,2]   , "}" ,sep="" ) ,sep="," )
                        ii = ii + 1
                    }

                    return(paste("[",retStr,"]"))
                } else {
                    return ('[]')
                }
            }
        } else {
            return('err5')
        }
    } else {
        return('err6')
    }
}

if(length(args) >=4){
    cat(work_fpeaks(args[1], args[2], args[3], args[4], 
        length(args) < 5 || as.logical(args[5]), 
        length(args) >= 6 && as.logical(args[6])
    ))
} else {
    cat('Usage:\n    fpeaks.R file threshold bin_size frequency [normch] [normms]\n')
    quit(save="no",status=-1,runLast=FALSE)
}
